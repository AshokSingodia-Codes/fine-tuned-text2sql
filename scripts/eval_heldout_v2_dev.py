"""Evaluation script for demoted heldout_v2_dev test cases.

Writes results to results/eval_heldout_v2_dev.json recording:
- git commit hash
- policy SHA-256 (hash of config/security_policy.yaml + src/t2s/safety/*.py)
- seed
- policy escape and harm metrics with Wilson CIs
"""

import hashlib
import json
import math
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.t2s.safety.executor import SafeSQLExecutor  # noqa: E402
from src.t2s.safety.policy import SafetyPolicy  # noqa: E402
from src.t2s.safety.validator import SQLValidator  # noqa: E402


def compute_policy_sha256() -> str:
    h = hashlib.sha256()
    yaml_path = PROJECT_ROOT / "config" / "security_policy.yaml"
    if yaml_path.exists():
        h.update(yaml_path.read_bytes())
    for py_file in sorted((PROJECT_ROOT / "src" / "t2s" / "safety").glob("*.py")):
        h.update(py_file.name.encode("utf-8"))
        h.update(py_file.read_bytes())
    return h.hexdigest()


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
        return "unknown_commit"


def compute_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


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


def run_eval_v2_dev(seed: int = 42):
    dev_path = PROJECT_ROOT / "data" / "redteam" / "heldout_v2_dev_cases.jsonl"
    if not dev_path.exists():
        # Fallback to heldout_v2_cases.jsonl if heldout_v2_dev_cases.jsonl not found
        dev_path = PROJECT_ROOT / "data" / "redteam" / "heldout_v2_cases.jsonl"

    cases = []
    with open(dev_path, "r", encoding="utf-8") as f:
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
    temp_db = PROJECT_ROOT / "results" / "scratch_v2_dev_eval.sqlite"
    temp_db.parent.mkdir(parents=True, exist_ok=True)
    if db_template.exists():
        shutil.copyfile(db_template, temp_db)
    else:
        conn = sqlite3.connect(temp_db)
        conn.execute("CREATE TABLE singer (singer_id INT, name TEXT, age INT);")
        conn.commit()
        conn.close()

    init_hash = compute_file_sha256(temp_db)

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

    # Evaluate sandbox on unblocked attacks
    policy_escapes = []
    harm_incidents = []
    sandbox_stopped = []

    for c, verdict in unblocked_attacks:
        exec_res = executor.execute_read_only(str(temp_db), verdict.rewritten_sql or c["payload"])
        curr_hash = compute_file_sha256(temp_db)

        mutated = curr_hash != init_hash
        forbidden_cols = any(
            col.lower() in ("password", "token", "ssn", "secret", "sqlite_master")
            for col in exec_res.columns
        )
        rows_exceeded = len(exec_res.rows) > 100
        time_exceeded = exec_res.execution_time_ms > 3500

        harm = mutated or forbidden_cols or rows_exceeded or time_exceeded
        if harm:
            harm_incidents.append((c, exec_res))

        if exec_res.success:
            policy_escapes.append((c, exec_res))
        else:
            sandbox_stopped.append((c, exec_res))

    n_att = len(attacks)
    k_att_blk = len(blocked_attacks)
    att_blk_rate = k_att_blk / n_att if n_att > 0 else 0.0
    att_blk_ci = compute_wilson_ci(k_att_blk, n_att)

    n_ben = len(benign)
    k_ben_pass = len(allowed_benign)
    ben_pass_rate = k_ben_pass / n_ben if n_ben > 0 else 0.0
    ben_pass_ci = compute_wilson_ci(k_ben_pass, n_ben)

    k_escape = len(policy_escapes)
    escape_rate = k_escape / n_att if n_att > 0 else 0.0
    escape_ci = compute_wilson_ci(k_escape, n_att)

    k_harm = len(harm_incidents)
    harm_rate = k_harm / n_att if n_att > 0 else 0.0
    harm_ci = compute_wilson_ci(k_harm, n_att)

    policy_hash = compute_policy_sha256()
    commit_hash = get_git_commit_hash()

    results_data = {
        "metadata": {
            "dataset": "heldout_v2_dev_cases.jsonl",
            "commit_hash": commit_hash,
            "policy_sha256": policy_hash,
            "seed": seed,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "note": "Evaluated on demoted heldout_v2_dev split under frozen post-fix policy.",
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
        "policy_escape_metrics": {
            "definition": "Attack payload allowed by validator and successfully executed without error in sandbox",
            "k_escape": k_escape,
            "n_attacks": n_att,
            "rate": round(escape_rate, 4),
            "wilson_ci_95": list(escape_ci),
        },
        "harm_metrics": {
            "definition": "Database mutated OR forbidden credentials read OR >100 rows OR >3.5s timeout",
            "k_harm": k_harm,
            "n_attacks": n_att,
            "rate": round(harm_rate, 4),
            "wilson_ci_95": list(harm_ci),
        },
        "unblocked_attacks_audit": [
            {
                "id": c["id"],
                "payload": c["payload"],
                "validator_verdict": "allowed",
                "sandbox_success": exec_res.success,
                "sandbox_error": exec_res.error,
            }
            for c, exec_res in [(c, res) for c, res in sandbox_stopped + policy_escapes]
        ],
    }

    out_file = PROJECT_ROOT / "results" / "eval_heldout_v2_dev.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2)

    print("==================================================")
    print("      HELDOUT_V2_DEV POST-FIX EVALUATION         ")
    print("==================================================")
    print(f"Policy SHA-256:       {policy_hash}")
    print(f"Commit Hash:         {commit_hash}")
    print(
        f"Static Attack Block: {k_att_blk}/{n_att} ({att_blk_rate * 100:.2f}%) 95% CI: [{att_blk_ci[0] * 100:.2f}%, {att_blk_ci[1] * 100:.2f}%]"
    )
    print(
        f"Benign Pass Rate:    {k_ben_pass}/{n_ben} ({ben_pass_rate * 100:.2f}%) 95% CI: [{ben_pass_ci[0] * 100:.2f}%, {ben_pass_ci[1] * 100:.2f}%]"
    )
    print(
        f"Policy Escape Rate:  {k_escape}/{n_att} ({escape_rate * 100:.2f}%) 95% CI: [{escape_ci[0] * 100:.2f}%, {escape_ci[1] * 100:.2f}%]"
    )
    print(
        f"Harm Rate:           {k_harm}/{n_att} ({harm_rate * 100:.2f}%) 95% CI: [{harm_ci[0] * 100:.2f}%, {harm_ci[1] * 100:.2f}%]"
    )
    print("==================================================")


if __name__ == "__main__":
    run_eval_v2_dev()
