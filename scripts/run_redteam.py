"""Run Red-Team Security Evaluation on SQL Safety Layer."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.t2s.safety.executor import SafeSQLExecutor  # noqa: E402
from src.t2s.safety.policy import SafetyPolicy  # noqa: E402
from src.t2s.safety.redteam_cases import REDTEAM_CASES  # noqa: E402
from src.t2s.safety.validator import SQLValidator  # noqa: E402


def run_redteam_suite(
    output_path: str = "reports/metrics_safety.json",
    gold_sql_path: str = "data/raw/spider/dev_gold.sql",
) -> Dict[str, Any]:
    print("\n========================================================")
    print("  RUNNING RED-TEAM SECURITY SUITE & FALSE-BLOCK CHECK")
    print("========================================================")

    policy = SafetyPolicy.load()
    validator = SQLValidator(policy)
    executor = SafeSQLExecutor(timeout_seconds=policy.timeout_seconds, max_rows=policy.max_row_limit)

    results_by_category: Dict[str, Dict[str, int]] = {}
    passed_cases = 0
    total_cases = len(REDTEAM_CASES)

    detailed_cases = []

    for case in REDTEAM_CASES:
        cat = case.category
        if cat not in results_by_category:
            results_by_category[cat] = {"total": 0, "correct_outcome": 0}
        results_by_category[cat]["total"] += 1

        verdict = validator.validate(case.prompt_or_sql)
        is_blocked = not verdict.allowed

        # Check expected vs actual
        success = (is_blocked == case.expected_blocked)
        if success:
            passed_cases += 1
            results_by_category[cat]["correct_outcome"] += 1

        detailed_cases.append(
            {
                "id": case.id,
                "category": case.category,
                "sql": case.prompt_or_sql,
                "expected_blocked": case.expected_blocked,
                "actual_blocked": is_blocked,
                "reasons": verdict.reasons,
                "rewritten_sql": verdict.rewritten_sql,
                "passed": success,
            }
        )

    block_rate_by_cat = {}
    for cat, stats in results_by_category.items():
        tot = stats["total"]
        acc = stats["correct_outcome"] / tot if tot > 0 else 0.0
        block_rate_by_cat[cat] = {
            "total": tot,
            "correct_outcomes": stats["correct_outcome"],
            "accuracy": round(acc, 4),
        }

    # False-block evaluation on Dev Gold SQL
    gold_total = 0
    gold_blocked = 0
    gold_path = Path(gold_sql_path)
    if gold_path.exists():
        with open(gold_path, "r", encoding="utf-8") as f:
            for line in f:
                sql_line = line.strip()
                if sql_line:
                    gold_total += 1
                    # Extract gold query text
                    sql_text = sql_line.split("\t")[0]
                    v = validator.validate(sql_text)
                    if not v.allowed:
                        gold_blocked += 1

    false_block_rate = (gold_blocked / gold_total) if gold_total > 0 else 0.0

    summary = {
        "redteam_suite": {
            "total_test_cases": total_cases,
            "passed_test_cases": passed_cases,
            "overall_accuracy": round(passed_cases / total_cases, 4),
            "block_rate_by_category": block_rate_by_cat,
        },
        "false_block_check": {
            "gold_queries_tested": gold_total,
            "gold_queries_blocked": gold_blocked,
            "false_block_rate": round(false_block_rate, 4),
        },
        "detailed_results": detailed_cases,
    }

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved safety metrics report -> {out_p}")
    print(f"Red-Team Suite Accuracy: {passed_cases}/{total_cases} ({summary['redteam_suite']['overall_accuracy'] * 100:.1f}%)")
    print(f"False-Block Rate on Gold SQL: {false_block_rate * 100:.2f}% ({gold_blocked}/{gold_total})")
    print("========================================================\n")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/metrics_safety.json")
    args = parser.parse_args()

    run_redteam_suite(output_path=args.output)
