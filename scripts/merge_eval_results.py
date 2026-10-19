"""Merge individual config evaluation JSON files into unified results/eval_spider_latest.json.

Combines results for configs A, B, C, D if split into separate files.
"""

import datetime
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def merge_eval_results(results_dir: Path = PROJECT_ROOT / "results") -> Path:
    config_files = {
        "A": results_dir / "eval_spider_A.json",
        "B": results_dir / "eval_spider_B.json",
        "C": results_dir / "eval_spider_C.json",
        "D": results_dir / "eval_spider_D.json",
    }

    latest_file = results_dir / "eval_spider_latest.json"

    merged_configs = {}
    metadata = {
        "date": datetime.datetime.now().isoformat(),
        "git_commit_hash": "unknown_commit",
        "seed": 42,
        "dataset_split": "Spider dev",
        "eval_limit": None,
        "backend_used": "mixed",
    }

    # First check if separate config files exist
    found_any = False
    for cfg_id, cfg_path in config_files.items():
        if cfg_path.exists():
            found_any = True
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "configs" in data and cfg_id in data["configs"]:
                    merged_configs[cfg_id] = data["configs"][cfg_id]
                elif "config_id" in data and data["config_id"] == cfg_id:
                    merged_configs[cfg_id] = data
                if "metadata" in data:
                    metadata.update(data["metadata"])

    if not found_any and latest_file.exists():
        with open(latest_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
            merged_configs = existing.get("configs", {})
            metadata = existing.get("metadata", metadata)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {
        "metadata": metadata,
        "configs": merged_configs,
    }

    timestamped_file = results_dir / f"eval_spider_{timestamp}.json"
    with open(timestamped_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Merged evaluation results saved to:\n  - {timestamped_file}\n  - {latest_file}")
    return latest_file


if __name__ == "__main__":
    merge_eval_results()
