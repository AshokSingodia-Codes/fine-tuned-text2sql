"""Error analysis and generalization slicing for Text-to-SQL evaluation."""

import re
from typing import Any, Dict, List


def categorize_error(
    pred_sql: str,
    gold_sql: str,
    exec_success: bool,
    is_valid_sql: bool,
) -> str:
    """Categorize the type of failure for a predicted SQL query.

    Categories:
    - correct
    - syntax_error
    - missing_group_by
    - wrong_aggregation
    - wrong_join
    - wrong_column
    - value_mismatch
    - other_semantic_error
    """
    if exec_success:
        return "correct"
    if not is_valid_sql:
        return "syntax_error"

    pred_upper = pred_sql.upper()
    gold_upper = gold_sql.upper()

    # Check for GROUP BY mismatch
    if ("GROUP BY" in gold_upper) and ("GROUP BY" not in pred_upper):
        return "missing_group_by"

    # Check for aggregation functions (COUNT, SUM, AVG, MIN, MAX)
    agg_funcs = ["COUNT(", "SUM(", "AVG(", "MIN(", "MAX("]
    gold_aggs = [f for f in agg_funcs if f in gold_upper]
    pred_aggs = [f for f in agg_funcs if f in pred_upper]
    if gold_aggs != pred_aggs:
        return "wrong_aggregation"

    # Check for JOIN mismatch
    if ("JOIN" in gold_upper) and ("JOIN" not in pred_upper):
        return "wrong_join"

    # Check if WHERE clause values differ
    where_gold = re.findall(r"'[^']+'|\b\d+\b", gold_sql)
    where_pred = re.findall(r"'[^']+'|\b\d+\b", pred_sql)
    if where_gold != where_pred:
        return "value_mismatch"

    # Check column names mismatch heuristics
    return "other_semantic_error"


def compare_systems_diff(
    eval_a_results: List[Dict[str, Any]],
    eval_c_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Identify questions fixed or broken by System C compared to System A."""
    fixed = []
    broken = []
    both_correct = []
    both_wrong = []

    for idx, (res_a, res_c) in enumerate(zip(eval_a_results, eval_c_results)):
        a_match = res_a.get("exec_match", False)
        c_match = res_c.get("exec_match", False)
        q = res_c.get("question", f"Question #{idx}")
        db = res_c.get("db_id", "")

        item = {
            "index": idx,
            "db_id": db,
            "question": q,
            "gold": res_c.get("gold", ""),
            "pred_a": res_a.get("pred", ""),
            "pred_c": res_c.get("pred", ""),
        }

        if not a_match and c_match:
            fixed.append(item)
        elif a_match and not c_match:
            broken.append(item)
        elif a_match and c_match:
            both_correct.append(item)
        else:
            both_wrong.append(item)

    return {
        "fixed_count": len(fixed),
        "broken_count": len(broken),
        "both_correct_count": len(both_correct),
        "both_wrong_count": len(both_wrong),
        "fixed_questions": fixed[:20],  # sample up to 20
        "broken_questions": broken[:20],
    }


def compute_generalization_slices(detailed_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute accuracy sliced by database, SQL features (JOIN, GROUP BY, etc.)."""
    by_db: Dict[str, Dict[str, int]] = {}
    by_feature: Dict[str, Dict[str, int]] = {
        "has_join": {"total": 0, "correct": 0},
        "has_group_by": {"total": 0, "correct": 0},
        "has_order_by": {"total": 0, "correct": 0},
        "has_subquery": {"total": 0, "correct": 0},
    }

    for res in detailed_results:
        db = res.get("db_id", "unknown")
        correct = res.get("exec_match", False)

        if db not in by_db:
            by_db[db] = {"total": 0, "correct": 0}
        by_db[db]["total"] += 1
        if correct:
            by_db[db]["correct"] += 1

        gold = res.get("gold", "").upper()
        if "JOIN" in gold:
            by_feature["has_join"]["total"] += 1
            if correct:
                by_feature["has_join"]["correct"] += 1
        if "GROUP BY" in gold:
            by_feature["has_group_by"]["total"] += 1
            if correct:
                by_feature["has_group_by"]["correct"] += 1
        if "ORDER BY" in gold:
            by_feature["has_order_by"]["total"] += 1
            if correct:
                by_feature["has_order_by"]["correct"] += 1
        if "SELECT" in gold and gold.count("SELECT") > 1:
            by_feature["has_subquery"]["total"] += 1
            if correct:
                by_feature["has_subquery"]["correct"] += 1

    db_accuracy = {}
    for db, stats in by_db.items():
        tot = stats["total"]
        db_accuracy[db] = {
            "total": tot,
            "correct": stats["correct"],
            "accuracy": stats["correct"] / tot if tot > 0 else 0.0,
        }

    feature_accuracy = {}
    for feat, stats in by_feature.items():
        tot = stats["total"]
        feature_accuracy[feat] = {
            "total": tot,
            "correct": stats["correct"],
            "accuracy": stats["correct"] / tot if tot > 0 else 0.0,
        }

    return {
        "by_database": db_accuracy,
        "by_feature": feature_accuracy,
    }
