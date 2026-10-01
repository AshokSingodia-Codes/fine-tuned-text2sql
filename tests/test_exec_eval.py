"""Tests for internal execution evaluator and sanity checks."""

import json
import tempfile
from pathlib import Path

from src.t2s.eval.exec_eval import (
    compare_query_results,
    evaluate_predictions,
    execute_sql_query,
)


def test_gold_vs_gold_synthetic(fixture_db_path: str) -> None:
    gold_sql = "SELECT name, country FROM artists ORDER BY name;"
    ok, res, err = execute_sql_query(fixture_db_path, gold_sql)

    assert ok is True
    assert err is None
    assert len(res) == 2
    assert compare_query_results(res, res, gold_sql) is True


def test_empty_or_garbage_prediction(fixture_db_path: str) -> None:
    ok1, res1, err1 = execute_sql_query(fixture_db_path, "")
    assert ok1 is False

    ok2, res2, err2 = execute_sql_query(fixture_db_path, "NOT A VALID SQL STATEMENT;")
    assert ok2 is False
    assert err2 is not None


def test_subtly_wrong_where_fails(fixture_db_path: str) -> None:
    gold_sql = "SELECT name FROM artists WHERE country = 'UK';"
    pred_sql = "SELECT name FROM artists WHERE country = 'USA';"

    g_ok, g_res, _ = execute_sql_query(fixture_db_path, gold_sql)
    p_ok, p_res, _ = execute_sql_query(fixture_db_path, pred_sql)

    assert g_ok and p_ok
    assert compare_query_results(g_res, p_res, gold_sql) is False


def test_reordered_select_columns(fixture_db_path: str) -> None:
    gold_sql = "SELECT name, country FROM artists;"
    pred_sql = "SELECT country, name FROM artists;"

    g_ok, g_res, _ = execute_sql_query(fixture_db_path, gold_sql)
    p_ok, p_res, _ = execute_sql_query(fixture_db_path, pred_sql)

    assert g_ok and p_ok
    assert compare_query_results(g_res, p_res, gold_sql) is False


def test_gold_vs_gold_spider_dev() -> None:
    dev_jsonl = Path("data/processed/dev.jsonl")
    if not dev_jsonl.exists():
        return

    with open(dev_jsonl, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    gold_as_pred_records = []
    for r in records:
        gold_as_pred_records.append(
            {
                "db_id": r["db_id"],
                "question": r["question"],
                "gold": r["gold_sql"],
                "pred": r["gold_sql"],
                "latency_ms": 0.0,
                "tokens": 0,
            }
        )

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".jsonl") as f_tmp:
        for item in gold_as_pred_records:
            f_tmp.write(json.dumps(item) + "\n")
        tmp_name = f_tmp.name

    metrics = evaluate_predictions(tmp_name)
    Path(tmp_name).unlink(missing_ok=True)

    # Gold vs gold execution accuracy should be >= 99%
    assert metrics["exec_accuracy"] >= 0.99
