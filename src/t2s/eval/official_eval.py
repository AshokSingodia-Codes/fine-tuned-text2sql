"""Official test-suite-sql-eval wrapper."""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict


def run_official_evaluation(
    predictions_jsonl_path: str,
    gold_sql_path: str = "data/raw/spider/dev_gold.sql",
    tables_json_path: str = "data/raw/spider/tables.json",
    db_dir: str = "data/raw/spider/database",
    etype: str = "exec",
) -> Dict[str, Any]:
    pred_path = Path(predictions_jsonl_path)
    if not pred_path.exists():
        raise FileNotFoundError(f"Predictions file not found: {predictions_jsonl_path}")

    pred_queries = []
    gold_queries = []
    db_ids = []

    with open(pred_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                pred_queries.append(data.get("pred", "").replace("\n", " "))
                gold_queries.append(data.get("gold", "").replace("\n", " "))
                db_ids.append(data.get("db_id", ""))

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f_pred:
        for q in pred_queries:
            f_pred.write(q.strip() + "\n")
        temp_pred_file = f_pred.name

    if not Path(gold_sql_path).exists():
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".sql") as f_gold:
            for q, db in zip(gold_queries, db_ids):
                f_gold.write(f"{q.strip()}\t{db}\n")
            temp_gold_file = f_gold.name
    else:
        temp_gold_file = gold_sql_path

    eval_script = Path("third_party/test-suite-sql-eval/evaluation.py")
    if not eval_script.exists():
        raise FileNotFoundError(f"Official evaluation script not found at {eval_script}")

    cmd = [
        sys.executable,
        str(eval_script),
        "--gold",
        str(temp_gold_file),
        "--pred",
        str(temp_pred_file),
        "--db",
        str(db_dir),
        "--table",
        str(tables_json_path),
        "--etype",
        etype,
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        stdout = proc.stdout
    except subprocess.CalledProcessError as e:
        print(f"Official evaluation failed: {e.stderr}")
        stdout = e.stdout

    try:
        Path(temp_pred_file).unlink(missing_ok=True)
        if not Path(gold_sql_path).exists():
            Path(temp_gold_file).unlink(missing_ok=True)
    except Exception:
        pass

    results = parse_test_suite_output(stdout)
    results["raw_output"] = stdout
    return results


def parse_test_suite_output(output_text: str) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {
        "exec_accuracy": 0.0,
        "hardness_breakdown": {},
    }

    # Match execution accuracy line e.g. "execution 0.015 0.020 0.000 0.000 0.012"
    lines = output_text.splitlines()
    for line in lines:
        if line.strip().startswith("execution"):
            parts = line.split()
            if len(parts) >= 6:
                try:
                    easy = float(parts[1])
                    medium = float(parts[2])
                    hard = float(parts[3])
                    extra = float(parts[4])
                    all_acc = float(parts[5])

                    metrics["exec_accuracy"] = all_acc
                    metrics["hardness_breakdown"] = {
                        "easy": easy,
                        "medium": medium,
                        "hard": hard,
                        "extra": extra,
                        "all": all_acc,
                    }
                    return metrics
                except ValueError:
                    pass

    pattern = r"(?:exec(?:ution)?\s*acc(?:uracy)?|exact match)\s*[:=]\s*([\d\.]+)"
    exec_match = re.search(pattern, output_text, re.IGNORECASE)
    if exec_match:
        metrics["exec_accuracy"] = float(exec_match.group(1))

    return metrics
