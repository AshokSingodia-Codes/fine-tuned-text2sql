"""Audit False-Positive Rate (FPR) on 1,034 Spider dev gold queries + 55 benign control cases.

Generates results/false_blocks.json with detailed root cause and accepted trade-off / fix justification.
"""

import json
import math
import sys
from pathlib import Path
from typing import Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.t2s.safety.policy import SafetyPolicy  # noqa: E402
from src.t2s.safety.validator import SQLValidator  # noqa: E402


def compute_wilson_ci(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    z = 1.959963984540054
    p_hat = k / n
    denom = 1.0 + (z**2) / n
    center = (p_hat + (z**2) / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt((p_hat * (1.0 - p_hat) / n) + (z**2) / (4.0 * (n**2)))
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return (round(lower, 4), round(upper, 4))


def main():
    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)

    # 1. Spider dev gold queries
    dev_path = PROJECT_ROOT / "data" / "raw" / "spider" / "dev.json"
    with open(dev_path, "r", encoding="utf-8") as f:
        spider_dev = json.load(f)

    # 2. Benign red-team controls
    redteam_path = PROJECT_ROOT / "data" / "redteam" / "redteam_cases.jsonl"
    benign_cases = []
    if redteam_path.exists():
        with open(redteam_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    c = json.loads(line)
                    if c["category"] == "benign":
                        benign_cases.append(c)

    all_legitimate = []
    for item in spider_dev:
        all_legitimate.append(
            {
                "source": "spider_dev",
                "id": f"SPIDER_{item.get('db_id', '')}_{len(all_legitimate)}",
                "db_id": item.get("db_id", ""),
                "question": item.get("question", ""),
                "sql": item["query"],
            }
        )
    for b in benign_cases:
        all_legitimate.append(
            {
                "source": f"redteam_{b['split']}",
                "id": b["id"],
                "db_id": "test",
                "question": b.get("rationale", ""),
                "sql": b["payload"],
            }
        )

    blocked = []
    for item in all_legitimate:
        sql = item["sql"]
        verdict = validator.validate(sql)
        if not verdict.allowed:
            root_causes = []
            trade_offs = []
            for r in verdict.reasons:
                if "exceeds max allowed joins" in r:
                    root_causes.append(
                        "Complexity limit: Query has more joins in a single block than policy.max_joins"
                    )
                    trade_offs.append(
                        "Accepted trade-off: Deep multi-table joins are capped to prevent Cartesian explosion and resource exhaustion."
                    )
                elif "sensitive column" in r:
                    root_causes.append(f"Column denylist match: {r}")
                    trade_offs.append(
                        "Accepted trade-off: Column names matching credentials/PII are blocked by strict security policy."
                    )
                elif "SQL comments" in r:
                    root_causes.append("Comment token present in input")
                    trade_offs.append(
                        "Accepted trade-off: Comments are disallowed to prevent comment smuggling attacks."
                    )
                elif "Multiple SQL statements" in r:
                    root_causes.append("Multiple statements or unescaped semicolon")
                    trade_offs.append(
                        "Security requirement: Only single queries permitted to prevent stacked injection."
                    )
                else:
                    root_causes.append(r)
                    trade_offs.append("Security rule enforcement.")

            blocked.append(
                {
                    "id": item["id"],
                    "source": item["source"],
                    "db_id": item["db_id"],
                    "question": item["question"],
                    "sql": sql,
                    "violated_rules": verdict.reasons,
                    "root_cause": "; ".join(root_causes),
                    "resolution_or_tradeoff": "; ".join(trade_offs),
                }
            )

    n_total = len(all_legitimate)
    k_blocked = len(blocked)
    fpr = k_blocked / n_total if n_total > 0 else 0.0
    fpr_ci = compute_wilson_ci(k_blocked, n_total)

    # Spider dev alone
    spider_blocked = [b for b in blocked if b["source"] == "spider_dev"]
    n_spider = len(spider_dev)
    k_spider = len(spider_blocked)
    spider_fpr = k_spider / n_spider if n_spider > 0 else 0.0
    spider_ci = compute_wilson_ci(k_spider, n_spider)

    # Compute combined policy hash
    import hashlib

    def compute_policy_sha256() -> str:
        h = hashlib.sha256()
        yaml_path = PROJECT_ROOT / "config" / "security_policy.yaml"
        if yaml_path.exists():
            h.update(yaml_path.read_bytes())
        for py_file in sorted((PROJECT_ROOT / "src" / "t2s" / "safety").glob("*.py")):
            h.update(py_file.name.encode("utf-8"))
            h.update(py_file.read_bytes())
        return h.hexdigest()

    policy_hash = compute_policy_sha256()

    output = {
        "metadata": {
            "policy_sha256": policy_hash,
            "commit_hash": "2fb1f36b01574f919f11c6ef17f57c31b5406591",
            "seed": 42,
        },
        "summary": {
            "total_legitimate_queries": n_total,
            "blocked_count": k_blocked,
            "false_positive_rate": round(fpr, 4),
            "wilson_ci_95": list(fpr_ci),
            "spider_dev_alone": {
                "n": n_spider,
                "k_blocked": k_spider,
                "fpr": round(spider_fpr, 4),
                "wilson_ci_95": list(spider_ci),
            },
            "benign_controls_alone": {
                "n": len(benign_cases),
                "k_blocked": k_blocked - k_spider,
                "fpr": round(
                    (k_blocked - k_spider) / len(benign_cases) if benign_cases else 0.0, 4
                ),
            },
        },
        "blocked_queries": blocked,
    }

    out_file = PROJECT_ROOT / "results" / "false_blocks.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("==================================================================")
    print("                 FALSE-POSITIVE RATE AUDIT                       ")
    print("==================================================================")
    print(
        f"Total Evaluated:    {n_total} queries (Spider Dev: {n_spider}, Benign Controls: {len(benign_cases)})"
    )
    print(f"Blocked Queries:    {k_blocked}")
    print(
        f"Overall FPR:        {fpr * 100:.2f}% ({k_blocked}/{n_total}) [95% CI: {fpr_ci[0] * 100:.2f}% - {fpr_ci[1] * 100:.2f}%]"
    )
    print(
        f"Spider Dev FPR:     {spider_fpr * 100:.2f}% ({k_spider}/{n_spider}) [95% CI: {spider_ci[0] * 100:.2f}% - {spider_ci[1] * 100:.2f}%]"
    )
    print(f"Results written to: {out_file}")
    print("==================================================================")


if __name__ == "__main__":
    main()
