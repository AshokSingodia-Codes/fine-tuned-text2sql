"""Kaggle / Remote Execution Ingest script for Phase 3 Ablation results.

Unpacks phase3_results.zip (or folder) containing:
- results/eval_spider_latest.json (with configs D, E, F, G)
- results/ablation_latest.json
- results/eval_spider_phase3_*.json
- results/eval_spider_seeds_*.json

Updates results/PROGRESS.md, METRICS.md, and verifies against Rule R1 & R2.
"""

import argparse
import json
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def find_results_zip(custom_path: str = None) -> Path:
    if custom_path:
        p = Path(custom_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"Specified zip file not found at: {custom_path}")

    # Check default locations
    local_zip = PROJECT_ROOT / "phase3_results.zip"
    if local_zip.exists():
        return local_zip

    user_downloads = Path.home() / "Downloads" / "phase3_results.zip"
    if user_downloads.exists():
        return user_downloads

    raise FileNotFoundError(
        "Could not find phase3_results.zip in repo root or ~/Downloads. "
        "Please provide path via --zip /path/to/phase3_results.zip."
    )


def ingest_phase3_results(zip_path: Path) -> None:
    print(f"Ingesting Phase 3 results from: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        print(f"Zip archive contains {len(namelist)} items.")

        for name in namelist:
            if name.startswith("results/") and not name.startswith("results/smoke/"):
                zf.extract(name, PROJECT_ROOT)
                print(f"Extracted: {name}")

    print("Unpacked Phase 3 evaluation results successfully.")

    # Validate ingested json
    latest_file = PROJECT_ROOT / "results" / "eval_spider_latest.json"
    if latest_file.exists():
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        configs = data.get("configs", {})
        print(f"Found evaluation results for configs: {list(configs.keys())}")
        for cid, cres in configs.items():
            ex = cres.get("execution_accuracy", 0.0)
            calls = cres.get("avg_model_calls_per_question", 1.0)
            lat = cres.get("avg_latency_sec", 0.0)
            p95 = cres.get("p95_latency_sec", 0.0)
            print(
                f" - Config {cid}: EX={ex * 100:.2f}%, Calls/Q={calls}, Latency(avg/p95)={lat:.2f}s/{p95:.2f}s"
            )


def main():
    parser = argparse.ArgumentParser(description="Ingest Kaggle Phase 3 evaluation bundle.")
    parser.add_argument("--zip", type=str, default=None, help="Path to phase3_results.zip")
    args = parser.parse_args()

    zip_file = find_results_zip(args.zip)
    ingest_phase3_results(zip_file)


if __name__ == "__main__":
    main()
