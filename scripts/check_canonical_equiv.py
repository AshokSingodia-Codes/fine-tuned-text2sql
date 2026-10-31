"""Semantic preservation test between original Spider dev gold SQL and validator canonical SQL.

Evaluates all 1,034 Spider dev queries:
1. Validates original gold SQL through SQLValidator.
2. If allowed and rewritten, executes both original gold SQL and canonical SQL in sandbox.
3. Compares result sets (order-sensitive if ORDER BY in query, otherwise multiset equality).
4. Records any mismatch with detailed reasons to results/canonical_equiv.json.
"""

import json
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.t2s.safety.policy import SafetyPolicy  # noqa: E402
from src.t2s.safety.validator import SQLValidator  # noqa: E402


def get_git_commit_hash() -> str:
    env_sha = os.environ.get("COMMIT_SHA")
    if env_sha:
        return env_sha.strip()
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"


def compute_policy_sha256() -> str:
    import hashlib

    h = hashlib.sha256()
    yaml_path = PROJECT_ROOT / "config" / "security_policy.yaml"
    if yaml_path.exists():
        h.update(yaml_path.read_bytes())
    for py_file in sorted((PROJECT_ROOT / "src" / "t2s" / "safety").glob("*.py")):
        h.update(py_file.name.encode("utf-8"))
        h.update(py_file.read_bytes())
    return h.hexdigest()


def execute_query(
    db_path: Path, sql: str, timeout: float = 3.0
) -> Tuple[bool, Optional[List[Tuple[Any, ...]]], Optional[str]]:
    if not db_path.exists():
        return False, None, f"Database not found: {db_path}"
    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=timeout)
        cur = conn.cursor()
        cur.execute(sql)
        res = cur.fetchall()
        conn.close()
        return True, res, None
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, None, str(e)


def compare_results(
    orig_res: Optional[List[Tuple[Any, ...]]],
    canon_res: Optional[List[Tuple[Any, ...]]],
    sql: str,
) -> bool:
    if orig_res is None or canon_res is None:
        return False
    if "ORDER BY" in sql.upper():
        return orig_res == canon_res
    try:
        return Counter(orig_res) == Counter(canon_res)
    except Exception:
        return Counter(str(r) for r in orig_res) == Counter(str(r) for r in canon_res)


def main():
    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)

    dev_path = PROJECT_ROOT / "data" / "raw" / "spider" / "dev.json"
    db_base = PROJECT_ROOT / "data" / "raw" / "spider" / "database"

    with open(dev_path, "r", encoding="utf-8") as f:
        spider_dev = json.load(f)

    total_queries = len(spider_dev)
    blocked_by_validator = []
    execution_failures = []
    semantic_mismatches = []
    exact_matches = 0
    semantic_matches = 0

    for idx, item in enumerate(spider_dev):
        db_id = item["db_id"]
        gold_sql = item["query"]
        question = item.get("question", "")
        db_path = db_base / db_id / f"{db_id}.sqlite"

        # Validate
        v_res = validator.validate(gold_sql)
        if not v_res.allowed:
            blocked_by_validator.append(
                {
                    "idx": idx,
                    "db_id": db_id,
                    "question": question,
                    "gold_sql": gold_sql,
                    "reasons": v_res.reasons,
                }
            )
            continue

        canon_sql = v_res.rewritten_sql or gold_sql

        # Execute original
        o_ok, o_res, o_err = execute_query(db_path, gold_sql)
        c_ok, c_res, c_err = execute_query(db_path, canon_sql)

        if not o_ok or not c_ok:
            execution_failures.append(
                {
                    "idx": idx,
                    "db_id": db_id,
                    "gold_sql": gold_sql,
                    "canon_sql": canon_sql,
                    "orig_error": o_err,
                    "canon_error": c_err,
                }
            )
            continue

        if gold_sql.strip().lower() == canon_sql.strip().lower():
            exact_matches += 1

        is_equiv = compare_results(o_res, c_res, gold_sql)
        if is_equiv:
            semantic_matches += 1
        else:
            semantic_mismatches.append(
                {
                    "idx": idx,
                    "db_id": db_id,
                    "question": question,
                    "gold_sql": gold_sql,
                    "canon_sql": canon_sql,
                    "orig_row_count": len(o_res) if o_res else 0,
                    "canon_row_count": len(c_res) if c_res else 0,
                    "sample_orig_rows": o_res[:3] if o_res else [],
                    "sample_canon_rows": c_res[:3] if c_res else [],
                    "reason": "Result sets differ between original gold and validator canonical SQL",
                }
            )

    output = {
        "metadata": {
            "dataset": "spider_dev",
            "total_queries": total_queries,
            "commit_hash": get_git_commit_hash(),
            "policy_sha256": compute_policy_sha256(),
            "seed": 42,
        },
        "summary": {
            "total_queries": total_queries,
            "blocked_by_validator": len(blocked_by_validator),
            "execution_failures": len(execution_failures),
            "semantic_matches": semantic_matches,
            "semantic_mismatches": len(semantic_mismatches),
            "equivalence_rate_of_allowed": (
                round(semantic_matches / (total_queries - len(blocked_by_validator)), 4)
                if (total_queries - len(blocked_by_validator)) > 0
                else 0.0
            ),
        },
        "blocked_by_validator": blocked_by_validator,
        "execution_failures": execution_failures,
        "semantic_mismatches": semantic_mismatches,
    }

    out_file = PROJECT_ROOT / "results" / "canonical_equiv.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print("==================================================")
    print("      SEMANTIC PRESERVATION (GOLD vs CANONICAL)   ")
    print("==================================================")
    print(f"Total Evaluated:        {total_queries}")
    print(f"Blocked by Validator:   {len(blocked_by_validator)}")
    print(f"Execution Failures:     {len(execution_failures)}")
    print(f"Semantic Matches:       {semantic_matches}")
    print(f"Semantic Mismatches:    {len(semantic_mismatches)}")
    print(f"Equivalence Rate:       {output['summary']['equivalence_rate_of_allowed'] * 100:.2f}%")
    print(f"Results written to:     {out_file}")
    print("==================================================")


if __name__ == "__main__":
    main()
