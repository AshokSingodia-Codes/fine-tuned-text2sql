"""Evaluation script for text-to-SQL predictions."""

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.t2s.eval.exec_eval import evaluate_predictions  # noqa: E402
from src.t2s.eval.official_eval import run_official_evaluation  # noqa: E402
from src.t2s.eval.stats import bootstrap_confidence_interval  # noqa: E402


def evaluate(
    predictions_path: str,
    output_metrics_path: str = "reports/metrics.json",
    db_base_dir: str = "data/raw/spider/database",
    tables_json_path: str = "data/raw/spider/tables.json",
    gold_sql_path: str = "data/raw/spider/dev_gold.sql",
) -> None:
    print(f"Evaluating predictions from: {predictions_path}")

    internal_res = evaluate_predictions(
        predictions_path, db_base_dir=db_base_dir, timeout_seconds=3.0
    )

    detailed = internal_res.get("detailed_results", [])
    exec_successes = [item["exec_match"] for item in detailed]
    mean_acc, ci_low, ci_high = bootstrap_confidence_interval(exec_successes)

    official_res = {}
    try:
        official_res = run_official_evaluation(
            predictions_path,
            gold_sql_path=gold_sql_path,
            tables_json_path=tables_json_path,
            db_dir=db_base_dir,
        )
    except Exception as e:
        print(f"Warning: Official evaluator failed: {e}")

    summary = {
        "predictions_file": predictions_path,
        "total_examples": internal_res["total_examples"],
        "internal_eval": {
            "exec_accuracy": internal_res["exec_accuracy"],
            "valid_sql_rate": internal_res["valid_sql_rate"],
            "exact_match_accuracy": internal_res["exact_match_accuracy"],
            "confidence_interval_95": {
                "mean": mean_acc,
                "ci_low": ci_low,
                "ci_high": ci_high,
            },
        },
        "official_eval": official_res,
    }

    out_p = Path(output_metrics_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Saved evaluation metrics to: {out_p}")
    print(
        f"Internal Exec Acc: {internal_res['exec_accuracy']:.4f} "
        f"(95% CI: [{ci_low:.4f}, {ci_high:.4f}])"
    )
    print(f"Valid SQL Rate: {internal_res['valid_sql_rate']:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", default="data/processed/dev.jsonl")
    parser.add_argument("--output", default="reports/metrics.json")
    args = parser.parse_args()

    evaluate(args.predictions, args.output)
