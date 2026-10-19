"""Fast internal SQL execution evaluator."""

import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def execute_sql_query(
    db_path: str, sql_query: str, timeout_seconds: float = 3.0
) -> Tuple[bool, Optional[List[Tuple[Any, ...]]], Optional[str]]:
    path = Path(db_path)
    if not path.exists():
        return False, None, f"Database file not found: {db_path}"

    if not sql_query or not sql_query.strip():
        return False, None, "Empty SQL query"

    conn = None
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=timeout_seconds)
        cursor = conn.cursor()
        cursor.execute(sql_query)
        results = cursor.fetchall()
        conn.close()
        return True, results, None
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, None, str(e)


def compare_query_results(
    gold_results: Optional[List[Tuple[Any, ...]]],
    pred_results: Optional[List[Tuple[Any, ...]]],
    gold_sql: str,
) -> bool:
    if gold_results is None or pred_results is None:
        return False

    is_order_sensitive = "ORDER BY" in gold_sql.upper()

    if is_order_sensitive:
        return gold_results == pred_results
    else:
        try:
            return Counter(gold_results) == Counter(pred_results)
        except Exception:
            gold_str = Counter(str(r) for r in gold_results)
            pred_str = Counter(str(r) for r in pred_results)
            return gold_str == pred_str


def evaluate_predictions(
    predictions_jsonl_path: str,
    db_base_dir: str = "data/raw/spider/database",
    timeout_seconds: float = 3.0,
) -> Dict[str, Any]:
    path = Path(predictions_jsonl_path)
    if not path.exists():
        raise FileNotFoundError(f"Predictions file not found: {predictions_jsonl_path}")

    records: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    total = len(records)
    if total == 0:
        return {
            "total_examples": 0,
            "exec_accuracy": 0.0,
            "valid_sql_rate": 0.0,
            "exact_match_accuracy": 0.0,
        }

    exec_correct = 0
    valid_sql_count = 0
    exact_match_count = 0

    detailed_results = []

    for item in records:
        db_id = item["db_id"]
        gold_sql = item["gold"]
        pred_sql = item["pred"]
        db_path = str(Path(db_base_dir) / db_id / f"{db_id}.sqlite")

        exact_match = gold_sql.strip().lower().rstrip(";") == pred_sql.strip().lower().rstrip(";")
        if exact_match:
            exact_match_count += 1

        g_ok, g_res, g_err = execute_sql_query(db_path, gold_sql, timeout_seconds)
        p_ok, p_res, p_err = execute_sql_query(db_path, pred_sql, timeout_seconds)

        if p_ok:
            valid_sql_count += 1

        exec_match = False
        if g_ok and p_ok:
            exec_match = compare_query_results(g_res, p_res, gold_sql)
            if exec_match:
                exec_correct += 1

        detailed_results.append(
            {
                "db_id": db_id,
                "question": item.get("question", ""),
                "gold": gold_sql,
                "pred": pred_sql,
                "exact_match": exact_match,
                "exec_match": exec_match,
                "pred_valid": p_ok,
                "pred_error": p_err,
            }
        )

    return {
        "total_examples": total,
        "exec_accuracy": exec_correct / total,
        "valid_sql_rate": valid_sql_count / total,
        "exact_match_accuracy": exact_match_count / total,
        "exec_correct": exec_correct,
        "valid_sql_count": valid_sql_count,
        "exact_match_count": exact_match_count,
        "detailed_results": detailed_results,
    }
