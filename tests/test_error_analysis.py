"""Unit tests for error analysis, statistical comparisons, and generalization slicing."""

import pytest
from src.t2s.eval.error_analysis import (
    categorize_error,
    compare_systems_diff,
    compute_generalization_slices,
)
from src.t2s.eval.stats import bootstrap_confidence_interval, mcnemar_test


def test_categorize_error_types():
    assert categorize_error("SELECT * FROM t", "SELECT * FROM t", True, True) == "correct"
    assert categorize_error("INVALID SQL", "SELECT * FROM t", False, False) == "syntax_error"
    assert categorize_error("SELECT a FROM t", "SELECT a FROM t GROUP BY b", False, True) == "missing_group_by"
    assert categorize_error("SELECT COUNT(a) FROM t", "SELECT SUM(a) FROM t", False, True) == "wrong_aggregation"
    assert categorize_error("SELECT a FROM t", "SELECT a FROM t JOIN u ON t.id=u.id", False, True) == "wrong_join"
    assert categorize_error("SELECT a FROM t WHERE x=1", "SELECT a FROM t WHERE x=2", False, True) == "value_mismatch"


def test_compare_systems_diff():
    a_results = [
        {"question": "Q1", "exec_match": False},
        {"question": "Q2", "exec_match": True},
    ]
    c_results = [
        {"question": "Q1", "exec_match": True},   # fixed
        {"question": "Q2", "exec_match": False},  # broken
    ]
    diff = compare_systems_diff(a_results, c_results)
    assert diff["fixed_count"] == 1
    assert diff["broken_count"] == 1


def test_compute_generalization_slices():
    detailed = [
        {
            "db_id": "db1",
            "exec_match": True,
            "gold": "SELECT T1.a FROM t1 AS T1 JOIN t2 AS T2 ON T1.id = T2.id GROUP BY T1.a ORDER BY T1.a",
        },
        {
            "db_id": "db1",
            "exec_match": False,
            "gold": "SELECT a FROM t1 WHERE id IN (SELECT id FROM t2)",
        },
    ]
    slices = compute_generalization_slices(detailed)
    assert "db1" in slices["by_database"]
    assert slices["by_database"]["db1"]["total"] == 2
    assert slices["by_database"]["db1"]["correct"] == 1
    assert slices["by_feature"]["has_join"]["total"] == 1
    assert slices["by_feature"]["has_group_by"]["total"] == 1
    assert slices["by_feature"]["has_subquery"]["total"] == 1


def test_bootstrap_and_mcnemar():
    res_a = [True, False, True, False, True]
    res_b = [True, True, True, False, False]
    mean, low, high = bootstrap_confidence_interval(res_a)
    assert 0.0 <= low <= mean <= high <= 1.0

    mcnemar = mcnemar_test(res_a, res_b)
    assert "p_value" in mcnemar
    assert "significant" in mcnemar
