import json
import math
import shutil
import sqlite3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.t2s.safety.executor import SafeSQLExecutor  # noqa: E402
from src.t2s.safety.policy import SafetyPolicy  # noqa: E402
from src.t2s.safety.validator import SQLValidator  # noqa: E402


def compute_wilson_ci(k: int, n: int, confidence: float = 0.95):
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
    v2_path = PROJECT_ROOT / "data" / "redteam" / "heldout_v2_cases.jsonl"
    with open(v2_path, "r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)
    executor = SafeSQLExecutor(timeout_seconds=3.0, max_rows=100)

    db_template = (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "spider"
        / "database"
        / "concert_singer"
        / "concert_singer.sqlite"
    )
    temp_db = PROJECT_ROOT / "results" / "scratch_v2_eval.sqlite"
    temp_db.parent.mkdir(parents=True, exist_ok=True)
    if db_template.exists():
        shutil.copyfile(db_template, temp_db)
    else:
        conn = sqlite3.connect(temp_db)
        conn.execute("CREATE TABLE singer (singer_id INT, name TEXT, age INT);")
        conn.commit()
        conn.close()

    attacks = [c for c in cases if c["category"] != "benign"]
    benign = [c for c in cases if c["category"] == "benign"]

    # Evaluate Validator on Attacks (Path A)
    blocked_attacks = []
    unblocked_attacks = []
    for c in attacks:
        verdict = validator.validate(c["payload"])
        if not verdict.allowed:
            blocked_attacks.append((c, verdict))
        else:
            unblocked_attacks.append((c, verdict))

    # Evaluate Validator on Benign Controls
    allowed_benign = []
    blocked_benign = []
    for c in benign:
        verdict = validator.validate(c["payload"])
        if verdict.allowed:
            allowed_benign.append((c, verdict))
        else:
            blocked_benign.append((c, verdict))

    # Evaluate Sandbox on Any Unblocked Attacks (Defense in Depth / Path D)
    sandbox_stopped_attacks = []
    sandbox_succeeded_attacks = []
    for c, verdict in unblocked_attacks:
        exec_res = executor.execute_read_only(str(temp_db), verdict.rewritten_sql or c["payload"])
        if not exec_res.success:
            sandbox_stopped_attacks.append((c, exec_res))
        else:
            sandbox_succeeded_attacks.append((c, exec_res))

    n_att = len(attacks)
    k_att_blk = len(blocked_attacks)
    att_blk_rate = k_att_blk / n_att if n_att > 0 else 0.0
    att_blk_ci = compute_wilson_ci(k_att_blk, n_att)

    n_ben = len(benign)
    k_ben_pass = len(allowed_benign)
    ben_pass_rate = k_ben_pass / n_ben if n_ben > 0 else 0.0
    ben_pass_ci = compute_wilson_ci(k_ben_pass, n_ben)

    # End-to-end attack success rate on heldout_v2
    k_att_succ = len(sandbox_succeeded_attacks)
    att_succ_rate = k_att_succ / n_att if n_att > 0 else 0.0

    out_data = {
        "metadata": {
            "dataset": "heldout_v2_cases.jsonl",
            "commit_hash": "2fb1f36b01574f919f11c6ef17f57c31b5406591",
            "total_cases": len(cases),
            "attack_cases": n_att,
            "benign_cases": n_ben,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": "Agent-authored heldout_v2 evaluation run exactly once without policy tuning.",
        },
        "validator_on_attacks": {
            "total": n_att,
            "blocked": k_att_blk,
            "rate": round(att_blk_rate, 4),
            "wilson_ci_95": list(att_blk_ci),
            "unblocked_case_ids": [c["id"] for c, _ in unblocked_attacks],
        },
        "validator_on_benign": {
            "total": n_ben,
            "passed": k_ben_pass,
            "rate": round(ben_pass_rate, 4),
            "wilson_ci_95": list(ben_pass_ci),
            "blocked_case_ids": [c["id"] for c, _ in blocked_benign],
        },
        "sandbox_defense_on_unblocked_attacks": {
            "unblocked_submitted": len(unblocked_attacks),
            "stopped_by_sandbox": len(sandbox_stopped_attacks),
            "succeeded_in_sandbox": k_att_succ,
            "end_to_end_attack_success_rate": round(att_succ_rate, 4),
        },
        "detailed_results": [
            {
                "id": c["id"],
                "category": c["category"],
                "expected": c["expected"],
                "validator_allowed": (
                    c in [x[0] for x in allowed_benign] or c in [x[0] for x in unblocked_attacks]
                ),
                "outcome": "correct"
                if (c["expected"] == "block" and c in [x[0] for x in blocked_attacks])
                or (c["expected"] == "allow" and c in [x[0] for x in allowed_benign])
                else "divergence",
            }
            for c in cases
        ],
    }

    out_file = PROJECT_ROOT / "results" / "eval_heldout_v2.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)

    print("==================================================")
    print("      HELDOUT_V2 ONE-SHOT EVALUATION REPORT       ")
    print("==================================================")
    print(f"Total Cases:            {len(cases)} (48 attacks, 24 benign)")
    print(
        f"Static Attack Block:    {k_att_blk}/{n_att} ({att_blk_rate * 100:.2f}%) 95% CI: [{att_blk_ci[0] * 100:.2f}%, {att_blk_ci[1] * 100:.2f}%]"
    )
    print(
        f"Benign Pass Rate:       {k_ben_pass}/{n_ben} ({ben_pass_rate * 100:.2f}%) 95% CI: [{ben_pass_ci[0] * 100:.2f}%, {ben_pass_ci[1] * 100:.2f}%]"
    )
    print(f"Sandbox Stopped:        {len(sandbox_stopped_attacks)}/{len(unblocked_attacks)}")
    print(f"Attack Success Count:   {k_att_succ}/{n_att} ({att_succ_rate * 100:.2f}%)")
    if unblocked_attacks:
        print(f"Unblocked Payloads: {[c['id'] for c, _ in unblocked_attacks]}")
    if blocked_benign:
        print(f"Blocked Benign Controls: {[c['id'] for c, _ in blocked_benign]}")
    print("==================================================")


if __name__ == "__main__":
    main()
