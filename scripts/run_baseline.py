"""Run zero-shot (System A) and few-shot (System B) baselines."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.t2s.data.prompts import build_prompt_messages  # noqa: E402
from src.t2s.eval.exec_eval import evaluate_predictions  # noqa: E402
from src.t2s.eval.official_eval import run_official_evaluation  # noqa: E402
from src.t2s.eval.stats import bootstrap_confidence_interval  # noqa: E402
from src.t2s.gen.backends import BaseBackend, get_backend  # noqa: E402
from src.t2s.gen.generate import clean_generated_sql  # noqa: E402


def get_few_shot_examples(train_jsonl_path: str, n_shots: int = 3) -> List[Dict[str, str]]:
    path = Path(train_jsonl_path)
    if not path.exists():
        return []

    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                prompt_msgs = item.get("prompt", [])
                schema_ddl = ""
                question = ""
                for msg in prompt_msgs:
                    if msg.get("role") == "user":
                        content = msg.get("content", "")
                        if "### SQLite Schema:\n" in content:
                            parts = content.split("### Question:\n")
                            schema_ddl = parts[0].replace("### SQLite Schema:\n", "").strip()
                            if len(parts) > 1:
                                question = parts[1].strip()

                examples.append(
                    {
                        "schema_ddl": schema_ddl,
                        "question": question or item.get("question", ""),
                        "query": item.get("gold_sql", ""),
                    }
                )
                if len(examples) >= n_shots:
                    break
    return examples


def run_baseline_system(
    input_jsonl_path: str,
    output_pred_path: str,
    output_metrics_path: str,
    backend: BaseBackend,
    system_name: str = "System A (Zero-shot)",
    is_few_shot: bool = False,
    train_jsonl_path: str = "data/processed/train.jsonl",
    max_samples: Optional[int] = None,
) -> Dict[str, Any]:
    print(f"\n--- Running Baseline {system_name} on {input_jsonl_path} ---")

    path = Path(input_jsonl_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {input_jsonl_path}")

    few_shots = get_few_shot_examples(train_jsonl_path, n_shots=3) if is_few_shot else None

    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    if max_samples and max_samples < len(records):
        records = records[:max_samples]

    predictions = []
    prompt_messages_list = []

    for item in records:
        prompt_msgs = item.get("prompt", [])
        schema_ddl = ""
        question = item.get("question", "")

        for msg in prompt_msgs:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if "### SQLite Schema:\n" in content:
                    parts = content.split("### Question:\n")
                    schema_ddl = parts[0].replace("### SQLite Schema:\n", "").strip()
                    if len(parts) > 1 and not question:
                        question = parts[1].strip()

        msgs = build_prompt_messages(schema_ddl, question, few_shot_examples=few_shots)
        prompt_messages_list.append(msgs)

    gen_outputs = backend.generate(prompt_messages_list)

    for item, gen_out in zip(records, gen_outputs):
        cleaned_sql = clean_generated_sql(gen_out["text"])
        predictions.append(
            {
                "db_id": item["db_id"],
                "question": item.get("question", ""),
                "gold": item.get("gold_sql", item.get("completion", [{}])[0].get("content", "")),
                "pred": cleaned_sql,
                "raw_pred": gen_out["text"],
                "latency_ms": gen_out["latency_ms"],
                "tokens": gen_out["tokens"],
            }
        )

    pred_path = Path(output_pred_path)
    pred_path.parent.mkdir(parents=True, exist_ok=True)
    with open(pred_path, "w", encoding="utf-8") as f:
        for pred in predictions:
            f.write(json.dumps(pred) + "\n")

    internal_res = evaluate_predictions(str(pred_path))
    detailed = internal_res.get("detailed_results", [])
    exec_successes = [it["exec_match"] for it in detailed]
    mean_acc, ci_low, ci_high = bootstrap_confidence_interval(exec_successes)

    official_res = {}
    try:
        official_res = run_official_evaluation(str(pred_path))
    except Exception as e:
        print(f"Official evaluation warning: {e}")

    summary = {
        "system_name": system_name,
        "input_dataset": input_jsonl_path,
        "total_samples": len(predictions),
        "is_partial_subset": max_samples is not None and max_samples < len(records),
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

    out_metrics_p = Path(output_metrics_path)
    out_metrics_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_metrics_p, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Metrics saved to {out_metrics_p}")
    print(f"Exec Acc: {internal_res['exec_accuracy']:.4f} (95% CI: [{ci_low:.4f}, {ci_high:.4f}])")
    print(f"Valid SQL Rate: {internal_res['valid_sql_rate']:.4f}")

    return summary


def run_all_baselines(
    backend_type: str = "mock",
    dataset_path: str = "data/processed/val.jsonl",
    max_samples: Optional[int] = None,
) -> None:
    backend = get_backend(backend_type)

    # Baseline A: Zero-shot
    run_baseline_system(
        input_jsonl_path=dataset_path,
        output_pred_path="reports/predictions_A.jsonl",
        output_metrics_path="reports/metrics_baseline_A.json",
        backend=backend,
        system_name="System A (Zero-shot)",
        is_few_shot=False,
        max_samples=max_samples,
    )

    # Baseline B: Few-shot (3 examples)
    run_baseline_system(
        input_jsonl_path=dataset_path,
        output_pred_path="reports/predictions_B.jsonl",
        output_metrics_path="reports/metrics_baseline_B.json",
        backend=backend,
        system_name="System B (Few-shot 3-ex)",
        is_few_shot=True,
        max_samples=max_samples,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backend", default="mock", choices=["mock", "transformers", "openai_compat"]
    )
    parser.add_argument("--dataset", default="data/processed/val.jsonl")
    parser.add_argument("--max_samples", type=int, default=None)
    args = parser.parse_args()

    run_all_baselines(
        backend_type=args.backend, dataset_path=args.dataset, max_samples=args.max_samples
    )
