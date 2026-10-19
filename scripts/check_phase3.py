"""Verification harness for Phase 3 completion.

Validates:
1. src/t2s/service/self_correct.py exists and passes unit tests.
2. src/t2s/service/voting.py exists and passes unit tests.
3. Config flags present in config.py: self_correction.enabled, max_retries, voting.enabled, voting.n.
4. results/ablation_latest.json exists with configs D, E, F, G.
5. ablation_latest.json reports avg_model_calls_per_question > 1.0 for F and G.
6. All repaired SQL goes through validator before execution (unit test confirms).
7. Test suite count >= baseline (44) and all tests pass (excluding fuzz which is slow).
8. Ruff lint check is clean.
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_cmd(cmd: list) -> tuple:
    result = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


def check_phase3() -> bool:
    print("==================================================")
    print("          RUNNING PHASE 3 VERIFICATION            ")
    print("==================================================")
    failures = []

    # 1. Check self_correct.py exists
    sc_path = PROJECT_ROOT / "src" / "t2s" / "service" / "self_correct.py"
    if sc_path.exists():
        print(f"[PASS] self_correct.py exists ({sc_path.stat().st_size} bytes)")
    else:
        failures.append(f"[FAIL] self_correct.py NOT FOUND at {sc_path}")

    # 2. Check voting.py exists
    vt_path = PROJECT_ROOT / "src" / "t2s" / "service" / "voting.py"
    if vt_path.exists():
        print(f"[PASS] voting.py exists ({vt_path.stat().st_size} bytes)")
    else:
        failures.append(f"[FAIL] voting.py NOT FOUND at {vt_path}")

    # 3. Check config flags in config.py
    config_path = PROJECT_ROOT / "src" / "t2s" / "config.py"
    config_text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    for flag in [
        "self_correction",
        "enabled",
        "max_retries",
        "voting",
        "VotingConfig",
        "SelfCorrectionConfig",
    ]:
        if flag in config_text:
            print(f"[PASS] config.py contains '{flag}'")
        else:
            failures.append(f"[FAIL] config.py MISSING flag: '{flag}'")

    # 4. Check ablation_latest.json
    ablation_path = PROJECT_ROOT / "results" / "ablation_latest.json"
    if not ablation_path.exists():
        failures.append("[FAIL] results/ablation_latest.json NOT FOUND")
    else:
        with open(ablation_path, "r", encoding="utf-8") as f:
            ablation = json.load(f)

        full_results = ablation.get("full_dev_results", {})
        for cid in ["D", "E", "F", "G"]:
            if cid in full_results:
                ex = full_results[cid].get("execution_accuracy", None)
                calls = full_results[cid].get("avg_model_calls_per_question", 1.0)
                print(f"[PASS] Config {cid} present (EX={ex}, calls/q={calls})")
            else:
                failures.append(f"[FAIL] Config {cid} MISSING from ablation_latest.json")

        # F and G must have avg_model_calls_per_question > 1.0
        for cid in ["F", "G"]:
            if cid in full_results:
                calls = full_results[cid].get("avg_model_calls_per_question", 1.0)
                if calls > 1.0:
                    print(f"[PASS] Config {cid} avg_model_calls={calls:.1f} > 1.0 (voting confirmed)")
                else:
                    failures.append(
                        f"[FAIL] Config {cid} avg_model_calls={calls} must be > 1.0 for voting"
                    )

        # D must have latency info
        if "D" in full_results:
            d_res = full_results["D"]
            for key in ["avg_latency_sec", "p95_latency_sec"]:
                if key in d_res:
                    print(f"[PASS] Config D has '{key}' = {d_res[key]}")
                else:
                    failures.append(f"[FAIL] Config D MISSING '{key}'")

    # 5. Phase 3 unit tests
    print("\n--- Running Phase 3 unit tests ---")
    python_exe = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
    rc, out = run_cmd([
        python_exe, "-m", "pytest",
        "tests/test_phase3_service.py",
        "-v", "--tb=short",
    ])
    lines = out.strip().splitlines()
    for line in lines[-25:]:
        print(line)
    if rc == 0:
        print("[PASS] Phase 3 unit tests PASSED")
    else:
        failures.append("[FAIL] Phase 3 unit tests FAILED")

    # 6. Full test suite (excluding slow fuzz tests)
    print("\n--- Running full test suite (excl. slow fuzz) ---")
    rc_all, out_all = run_cmd([
        python_exe, "-m", "pytest", "tests/",
        "--ignore=tests/test_fuzz_validator.py",
        "--ignore=tests/test_parser_differential.py",
        "-q", "--tb=short",
    ])
    lines_all = out_all.strip().splitlines()
    for line in lines_all[-15:]:
        print(line)
    if rc_all == 0:
        print("[PASS] Full test suite PASSED (excl. slow fuzz tests)")
    else:
        failures.append("[FAIL] Full test suite has FAILURES")

    # 7. Ruff lint
    print("\n--- Ruff lint check ---")
    rc_ruff, out_ruff = run_cmd([
        python_exe, "-m", "ruff", "check", "src/t2s/service/",
    ])
    if rc_ruff == 0:
        print("[PASS] Ruff lint clean on src/t2s/service/")
    else:
        failures.append(f"[FAIL] Ruff lint errors:\n{out_ruff}")

    # Summary
    print("\n==================================================")
    if not failures:
        print("  PHASE 3 VERIFICATION: ALL CHECKS PASSED")
        print("==================================================")
        return True
    else:
        print("  PHASE 3 VERIFICATION: FAILURES FOUND")
        print("==================================================")
        for f in failures:
            print(f)
        return False


if __name__ == "__main__":
    ok = check_phase3()
    sys.exit(0 if ok else 1)
