"""Verification harness for Phase 1 completion.

Checks adapter file size/validity, GGUF binary, evaluation results for configs A-D,
latency benchmarks, figure generation, data leakage, test suite, and doc consistency.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192 * 1024):
            h.update(chunk)
    return h.hexdigest()


def check_phase1() -> bool:
    print("==================================================")
    print("          RUNNING PHASE 1 VERIFICATION            ")
    print("==================================================")

    failures: List[str] = []
    exits_with_code_2 = False

    # Check 1: adapter_model.safetensors > 10 MB and no "PLACEHOLDER"
    adapter_path = PROJECT_ROOT / "models" / "qlora_adapter" / "adapter_model.safetensors"
    if not adapter_path.exists():
        failures.append("Check 1 FAIL: adapter_model.safetensors does not exist.")
    else:
        size_mb = adapter_path.stat().st_size / (1024 * 1024)
        if size_mb <= 10:
            failures.append(f"Check 1 FAIL: adapter size is {size_mb:.2f} MB (expected > 10 MB).")
        else:
            with open(adapter_path, "rb") as f:
                header = f.read(1024)
                if b"PLACEHOLDER" in header:
                    failures.append("Check 1 FAIL: adapter contains 'PLACEHOLDER' text.")
                else:
                    print(f"Check 1 PASS: Valid adapter safetensors ({size_mb:.2f} MB).")

    # Check 2: GGUF exists and > 1 GB
    gguf_files = list((PROJECT_ROOT / "models").glob("*.gguf"))
    if not gguf_files:
        failures.append("Check 2 FAIL: No .gguf file found in models/ directory.")
    else:
        gguf_path = gguf_files[0]
        gguf_mb = gguf_path.stat().st_size / (1024 * 1024)
        if gguf_mb <= 1000:
            failures.append(f"Check 2 FAIL: GGUF size is {gguf_mb:.2f} MB (expected > 1 GB).")
        else:
            sha256_hash = compute_sha256(gguf_path)
            print(
                f"Check 2 PASS: GGUF model found ({gguf_mb:.2f} MB, SHA256: {sha256_hash[:12]}...)."
            )

    # Check 3 & 4: eval_spider_latest.json has A, B, C, D with n==1034 & backend != mock
    eval_json = PROJECT_ROOT / "results" / "eval_spider_latest.json"
    configs_data = {}
    if not eval_json.exists():
        failures.append("Check 3 & 4 FAIL: results/eval_spider_latest.json missing.")
    else:
        with open(eval_json, "r", encoding="utf-8") as f:
            eval_payload = json.load(f)
            backend_used = eval_payload.get("metadata", {}).get("backend_used", "")
            configs_data = eval_payload.get("configs", {})

        if backend_used == "mock":
            failures.append("Check 4 FAIL: backend_used is 'mock' in eval_spider_latest.json.")
        else:
            print("Check 4 PASS: Real model backend recorded.")

        missing_cfgs = []
        for cfg_id in ["A", "B", "C", "D"]:
            if cfg_id not in configs_data:
                missing_cfgs.append(cfg_id)
            else:
                n = configs_data[cfg_id].get("total_examples", 0)
                if n != 1034:
                    failures.append(f"Check 3 FAIL: Config {cfg_id} n={n} (expected 1034).")

        if missing_cfgs:
            failures.append(
                f"Check 3 FAIL: Missing configs {missing_cfgs} in eval_spider_latest.json."
            )
        elif not any("Check 3 FAIL" in f for f in failures):
            print("Check 3 PASS: Configs A, B, C, D present with n=1034.")

    # Check 5: EX(C) >= EX(A)
    if "C" in configs_data and "A" in configs_data:
        ex_c = configs_data["C"].get("execution_accuracy", 0.0)
        ex_a = configs_data["A"].get("execution_accuracy", 0.0)
        if ex_c < ex_a:
            exits_with_code_2 = True
            failures.append(f"Check 5 FAIL: EX(C)={ex_c * 100:.2f}% < EX(A)={ex_a * 100:.2f}%.")
            print("\n--------------------------------------------------")
            print("DIAGNOSIS CHECKLIST (Fine-Tuned EX < Base Zero-Shot):")
            print("  1. Verify prompt template parity between training and eval_spider.py.")
            print("  2. Verify correct fine-tuned adapter weights were loaded.")
            print("  3. Check learning rate (default: 2e-4) and warmup ratio.")
            print("  4. Ensure chat template includes add_generation_prompt=True.")
            print("--------------------------------------------------\n")
        else:
            print(f"Check 5 PASS: EX(C)={ex_c * 100:.2f}% >= EX(A)={ex_a * 100:.2f}%.")

    # Check 6: EX(D) >= EX(C) - 3.0 percentage points
    if "C" in configs_data and "D" in configs_data:
        ex_c = configs_data["C"].get("execution_accuracy", 0.0) * 100
        ex_d = configs_data["D"].get("execution_accuracy", 0.0) * 100
        if ex_d < (ex_c - 3.0):
            failures.append(
                f"Check 6 FAIL: EX(D)={ex_d:.2f}% is lower than EX(C)-3.0% ({ex_c - 3.0:.2f}%)."
            )
        else:
            print(f"Check 6 PASS: EX(D)={ex_d:.2f}% within 3.0% of EX(C)={ex_c:.2f}%.")

    # Check 7: latency_latest.json metrics
    lat_json = PROJECT_ROOT / "results" / "latency_latest.json"
    if not lat_json.exists():
        failures.append("Check 7 FAIL: results/latency_latest.json missing.")
    else:
        with open(lat_json, "r", encoding="utf-8") as f:
            lat_data = json.load(f)
            metrics = lat_data.get("metrics", {})
            hw = lat_data.get("hardware", {})
            has_tokens = ("tokens_per_sec" in metrics) or ("tokens_per_second" in metrics)
            has_hw_desc = ("description" in hw) or ("os" in hw and "cpu_name" in hw)
            n_questions = lat_data.get("num_questions") or lat_data.get("metadata", {}).get(
                "sample_count", 0
            )
            base_keys = [
                "p50_latency_sec",
                "p95_latency_sec",
                "p99_latency_sec",
                "peak_rss_mb",
            ]
            if not all(k in metrics for k in base_keys) or not has_tokens or not has_hw_desc:
                failures.append(
                    "Check 7 FAIL: latency_latest.json missing required keys or hardware description."
                )
            elif n_questions < 200:
                failures.append(f"Check 7 FAIL: latency n={n_questions} (expected >= 200).")
            else:
                print("Check 7 PASS: Latency metrics valid (n >= 200).")

    # Check 8: results/figures/ex_comparison.png exists
    fig_path = PROJECT_ROOT / "results" / "figures" / "ex_comparison.png"
    if not fig_path.exists():
        failures.append("Check 8 FAIL: results/figures/ex_comparison.png does not exist.")
    else:
        print("Check 8 PASS: ex_comparison.png figure present.")

    # Check 9: check_leakage.py exits 0
    res_leak = subprocess.run(
        [sys.executable, "scripts/check_leakage.py"], capture_output=True, text=True
    )
    if res_leak.returncode != 0:
        failures.append("Check 9 FAIL: scripts/check_leakage.py exited with non-zero code.")
    else:
        print("Check 9 PASS: check_leakage.py returned 0.")

    # Check 10: pytest -q passes and ruff check . is clean
    res_pytest = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"], capture_output=True, text=True
    )
    if res_pytest.returncode != 0:
        failures.append("Check 10 FAIL: pytest -q failed.")
    res_ruff = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "."], capture_output=True, text=True
    )
    if res_ruff.returncode != 0:
        failures.append("Check 10 FAIL: ruff check . failed.")
    if res_pytest.returncode == 0 and res_ruff.returncode == 0:
        print("Check 10 PASS: pytest -q and ruff check . clean.")

    # Check 11: docs/EVALUATION.md numbers equal JSON values
    eval_doc = PROJECT_ROOT / "docs" / "EVALUATION.md"
    if not eval_doc.exists():
        failures.append("Check 11 FAIL: docs/EVALUATION.md missing.")
    else:
        with open(eval_doc, "r", encoding="utf-8") as f:
            doc_text = f.read()
        for cfg_id, cfg_info in configs_data.items():
            ex_pct = f"{cfg_info.get('execution_accuracy', 0.0) * 100:.2f}%"
            if ex_pct not in doc_text:
                failures.append(
                    f"Check 11 FAIL: EX percentage {ex_pct} for Config {cfg_id} not in docs/EVALUATION.md."
                )
                break
        else:
            print("Check 11 PASS: docs/EVALUATION.md numbers match JSON values.")

    print("==================================================")
    if not failures:
        print("PHASE 1: COMPLETE")
        # Update results/PROGRESS.md
        prog_file = PROJECT_ROOT / "results" / "PROGRESS.md"
        if prog_file.exists():
            with open(prog_file, "r", encoding="utf-8") as f:
                content = f.read()
            import re

            content = re.sub(r"🛑 BLOCKED", "✅ COMPLETED", content)
            content = re.sub(r"⚠️ SCRIPTS READY, NOT RUN", "✅ COMPLETED", content)
            with open(prog_file, "w", encoding="utf-8") as f:
                f.write(content)
            print("Updated results/PROGRESS.md (Phase 0 and Phase 1 = COMPLETED).")
        return True
    else:
        print("PHASE 1 VERIFICATION FAILED. Summary of issues:")
        for f in failures:
            print(f" - {f}")
        if exits_with_code_2:
            sys.exit(2)
        return False


if __name__ == "__main__":
    success = check_phase1()
    if not success:
        sys.exit(1)
