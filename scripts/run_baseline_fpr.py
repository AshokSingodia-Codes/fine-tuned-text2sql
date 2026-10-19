"""Compute baseline False-Positive Rate (FPR) on Spider dev gold queries."""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.t2s.safety.validator import SQLValidator  # noqa: E402


def main():
    dev_path = Path("data/raw/spider/dev.json")
    with open(dev_path, "r", encoding="utf-8") as f:
        dev_data = json.load(f)

    validator = SQLValidator()

    total = len(dev_data)
    blocked = []

    for i, item in enumerate(dev_data):
        sql = item["query"]
        db_id = item.get("db_id", "")
        question = item.get("question", "")
        verdict = validator.validate(sql)
        if not verdict.allowed:
            # Determine root causes
            root_causes = []
            for reason in verdict.reasons:
                if "exceeds max allowed joins" in reason:
                    root_causes.append(
                        "Complexity limit (max_joins > 5) exceeded on multi-table join"
                    )
                elif "Multiple SQL statements" in reason:
                    root_causes.append(
                        "Semicolon inside query or trailing semicolon parsing artifact"
                    )
                elif "SQL comments" in reason:
                    root_causes.append("Comment token present in query string")
                elif "Forbidden statement/keyword" in reason:
                    root_causes.append(
                        f"Forbidden keyword substring match in identifier/string: {reason}"
                    )
                elif "Root query type" in reason:
                    root_causes.append(
                        f"Root AST node was not recognized as SELECT/UNION/INTERSECT/EXCEPT: {reason}"
                    )
                elif "sensitive column" in reason:
                    root_causes.append(
                        f"Legitimate domain column matched denied sensitive column list: {reason}"
                    )
                elif "system/sensitive table" in reason:
                    root_causes.append(
                        f"Legitimate domain table matched denied system table list: {reason}"
                    )
                else:
                    root_causes.append(reason)

            blocked.append(
                {
                    "index": i,
                    "db_id": db_id,
                    "question": question,
                    "sql": sql,
                    "reasons": verdict.reasons,
                    "root_causes": root_causes,
                }
            )

    output = {
        "total_gold_queries": total,
        "blocked_count": len(blocked),
        "false_positive_rate": len(blocked) / total if total > 0 else 0.0,
        "blocked_queries": blocked,
    }

    out_path = Path("results/false_blocks_baseline.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"Total gold queries: {total}")
    print(f"Blocked queries: {len(blocked)} ({len(blocked) / total * 100:.2f}%)")
    for b in blocked[:10]:
        print(f"  - [{b['db_id']}] {b['sql']} -> {b['reasons']}")


if __name__ == "__main__":
    main()
