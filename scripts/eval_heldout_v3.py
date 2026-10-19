"""One-shot evaluation harness for independent heldout_v3 dataset.

Executes only after scripts/verify_heldout_v3.py succeeds.
"""

import json
import math
import shutil
import sqlite3
import subprocess
import sys
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


def run_eval_v3():
    v3_path = PROJECT_ROOT / "data" / "redteam" / "heldout_v3_cases.jsonl"
    if not v3_path.exists():
        print("ERROR: heldout_v3_cases.jsonl missing. Aborting.")
        sys.exit(1)

    # Enforce verification first
    res_verify = subprocess.run(
        [sys.executable, "scripts/verify_heldout_v3.py"], capture_output=True, text=True
    )
    if res_verify.returncode != 0:
        print("Verification failed:\n", res_verify.stdout, res_verify.stderr)
        sys.exit(1)

    cases = []
    with open(v3_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line))

    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)
    executor = SafeSQLExecutor(policy=policy, timeout_seconds=3.0, max_rows=100)

    db_template = (
        PROJECT_ROOT
        / "data"
        / "raw"
        / "spider"
        / "database"
        / "concert_singer"
        / "concert_singer.sqlite"
    )
    temp_db = PROJECT_ROOT / "results" / "scratch_v3_eval.sqlite"
    temp_db.parent.mkdir(parents=True, exist_ok=True)
    if db_template.exists():
        shutil.copyfile(db_template, temp_db)
    else:
        conn = sqlite3.connect(temp_db)
        conn.execute("CREATE TABLE singer (singer_id INT, name TEXT, age INT);")
        conn.commit()
        conn.close()

    attacks = [c for c in cases if c.get("category") != "benign"]
    benign = [c for c in cases if c.get("category") == "benign"]

    blocked_attacks = []
    unblocked_attacks = []
    for c in attacks:
        verdict = validator.validate(c["payload"])
        if not verdict.allowed:
            blocked_attacks.append((c, verdict))
        else:
            unblocked_attacks.append((c, verdict))

    allowed_benign = []
    blocked_benign = []
    for c in benign:
        verdict = validator.validate(c["payload"])
        if verdict.allowed:
            allowed_benign.append((c, verdict))
        else:
            blocked_benign.append((c, verdict))

    sandbox_stopped = []
    sandbox_success = []
    for c, verdict in unblocked_attacks:
        exec_res = executor.execute_read_only(str(temp_db), verdict.rewritten_sql or c["payload"])
        if not exec_res.success:
            sandbox_stopped.append((c, exec_res))
        else:
            sandbox_success.append((c, exec_res))

    n_att = len(attacks)
    k_att_blk = len(blocked_attacks)
    att_blk_rate = k_att_blk / n_att if n_att > 0 else 0.0
    att_blk_ci = compute_wilson_ci(k_att_blk, n_att)

    n_ben = len(benign)
    k_ben_pass = len(allowed_benign)
    ben_pass_rate = k_ben_pass / n_ben if n_ben > 0 else 0.0
    ben_pass_ci = compute_wilson_ci(k_ben_pass, n_ben)

    k_succ = len(sandbox_success)
    att_succ_rate = k_succ / n_att if n_att > 0 else 0.0

    print("==================================================")
    print("      HELDOUT_V3 ONE-SHOT EVALUATION REPORT       ")
    print("==================================================")
    print(f"Total Cases:         {len(cases)} ({n_att} attacks, {n_ben} benign)")
    print(
        f"Static Attack Block: {k_att_blk}/{n_att} ({att_blk_rate * 100:.2f}%) 95% CI: [{att_blk_ci[0] * 100:.2f}%, {att_blk_ci[1] * 100:.2f}%]"
    )
    print(
        f"Benign Pass Rate:    {k_ben_pass}/{n_ben} ({ben_pass_rate * 100:.2f}%) 95% CI: [{ben_pass_ci[0] * 100:.2f}%, {ben_pass_ci[1] * 100:.2f}%]"
    )
    print(f"Sandbox Stopped:     {len(sandbox_stopped)}/{len(unblocked_attacks)}")
    print(f"Attack Success Count:{k_succ}/{n_att} ({att_succ_rate * 100:.2f}%)")
    print("==================================================")


if __name__ == "__main__":
    run_eval_v3()
