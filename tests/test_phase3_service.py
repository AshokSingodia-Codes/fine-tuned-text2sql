"""Unit tests for Phase 3 Self-Correction and Voting services (S6 design requirements).

Requirements verified:
- Repair triggers on execution error (no such column/table, syntax error).
- Repair stops at max retries.
- Never executes unvalidated SQL.
- Never retries after a policy block (no attacker oracle).
- Client-facing attempts array is properly sanitized (ok, exec_error:<category>, blocked_by_policy).
- Voting ignores invalid/blocked candidates (a failing candidate can never win).
- Request time budget is strictly respected.
"""

import sqlite3
import time
from typing import Dict, List

import pytest

from src.t2s.safety.executor import SafeSQLExecutor
from src.t2s.safety.policy import SafetyPolicy
from src.t2s.safety.validator import SQLValidator
from src.t2s.service.self_correct import SelfCorrectionRunner, sanitize_attempt_status
from src.t2s.service.voting import ConsensusVoter


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_phase3.sqlite"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE users (id INT, username TEXT, salary REAL);")
    conn.execute("INSERT INTO users VALUES (1, 'alice', 50000.0), (2, 'bob', 60000.0);")
    conn.commit()
    conn.close()
    return str(db_file)


def test_self_correction_triggers_on_exec_error_and_succeeds(test_db):
    """Test S1: repair triggers on DB runtime error ('no such column') and repairs SQL."""
    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)
    executor = SafeSQLExecutor(policy=policy)
    runner = SelfCorrectionRunner(validator=validator, executor=executor, max_retries=2)

    # Initial query references non-existent column 'user_name'
    initial_sql = "SELECT user_name FROM users;"

    # Mock generator returns valid column 'username' on retry
    repair_called = []

    def mock_generate(msgs: List[Dict[str, str]]) -> str:
        repair_called.append(msgs)
        # Verify the repair prompt quoted the error as data and didn't mention policy rules
        user_prompt = msgs[-1]["content"]
        assert "no such column: user_name" in user_prompt
        assert "policy" not in user_prompt.lower()
        return "SELECT username FROM users;"

    base_msgs = [{"role": "user", "content": "Get usernames"}]
    result = runner.run(test_db, initial_sql, mock_generate, base_msgs)

    assert result.allowed
    assert result.retried
    assert len(repair_called) == 1
    assert result.final_sql == "SELECT username FROM users;"
    assert result.exec_res is not None and result.exec_res.success
    assert len(result.attempts) == 2

    # Attempt 0 was exec_error:no_such_column
    assert result.attempts[0].status == "exec_error:no_such_column"
    # Attempt 1 was ok
    assert result.attempts[1].status == "ok"


def test_self_correction_stops_at_max_retries(test_db):
    """Test S1: repair loop terminates when max_retries is reached."""
    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)
    executor = SafeSQLExecutor(policy=policy)
    runner = SelfCorrectionRunner(validator=validator, executor=executor, max_retries=2)

    calls = 0

    def mock_generate_broken(msgs: List[Dict[str, str]]) -> str:
        nonlocal calls
        calls += 1
        return f"SELECT nonexistent_{calls} FROM users;"

    base_msgs = [{"role": "user", "content": "Broken query"}]
    result = runner.run(test_db, "SELECT bad_col_0 FROM users;", mock_generate_broken, base_msgs)

    # Total attempts = 1 initial + 2 retries = 3
    assert len(result.attempts) == 3
    assert calls == 2
    assert not result.exec_res.success


def test_self_correction_never_retries_after_policy_block(test_db):
    """Test S1: NEVER retry after a policy block (denied table/column/stacked/DML).

    Doing so would give an attacker an oracle.
    """
    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)
    executor = SafeSQLExecutor(policy=policy)
    runner = SelfCorrectionRunner(validator=validator, executor=executor, max_retries=2)

    repair_invoked = False

    def mock_generate(msgs: List[Dict[str, str]]) -> str:
        nonlocal repair_invoked
        repair_invoked = True
        return "SELECT username FROM users;"

    # Malicious injection payload attempting stacked statement
    attack_sql = "SELECT username FROM users; DROP TABLE users;"

    base_msgs = [{"role": "user", "content": "Attack test"}]
    result = runner.run(test_db, attack_sql, mock_generate, base_msgs)

    # Must be blocked by policy immediately
    assert not result.allowed
    assert not repair_invoked, "Repair generator MUST NOT be called on policy block!"
    assert len(result.attempts) == 1
    assert result.attempts[0].status == "blocked_by_policy"


def test_sanitized_attempt_status_contains_no_internal_policy_details():
    """Test S2: client-facing attempt status is strictly sanitized."""
    assert sanitize_attempt_status(allowed=False, exec_success=False) == "blocked_by_policy"
    assert sanitize_attempt_status(allowed=True, exec_success=True) == "ok"
    assert (
        sanitize_attempt_status(
            allowed=True, exec_success=False, error_msg="no such column: secret"
        )
        == "exec_error:no_such_column"
    )
    assert (
        sanitize_attempt_status(
            allowed=True, exec_success=False, error_msg="no such table: secret_table"
        )
        == "exec_error:no_such_table"
    )
    assert (
        sanitize_attempt_status(
            allowed=True, exec_success=False, error_msg="near 'WHERE': syntax error"
        )
        == "exec_error:syntax_error"
    )


def test_voting_validates_all_candidates_first_and_ignores_invalid(test_db):
    """Test S3: validator checks ALL N candidates before executing any; invalid cannot win."""
    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)
    executor = SafeSQLExecutor(policy=policy)
    voter = ConsensusVoter(validator=validator, executor=executor)

    candidates = [
        "DROP TABLE users;",  # Blocked by policy (DML)
        "SELECT username FROM users WHERE salary > 100000;",  # Allowed, returns 0 rows
        "SELECT username FROM users ORDER BY salary ASC;",  # Allowed, returns (alice, bob)
        "SELECT username FROM users ORDER BY salary ASC;",  # Allowed, returns (alice, bob) - Majority (2 votes)
        "SELECT unhex('1234');",  # Blocked by policy (unhex)
    ]

    result = voter.select_best_candidate(test_db, candidates)

    assert result.winner_sql == "SELECT username FROM users ORDER BY salary ASC;"
    assert result.consensus_score == "2/5"
    assert not result.fallback_to_greedy
    # Candidate 0 and 4 are blocked
    assert not result.candidates[0].verdict.allowed
    assert not result.candidates[4].verdict.allowed
    assert result.candidates[0].exec_res is None  # Never executed


def test_voting_budget_timeout_stops_execution(test_db):
    """Test S3: total request budget stops execution and falls back gracefully."""
    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)
    executor = SafeSQLExecutor(policy=policy)
    # Set impossible budget (0.0001 seconds)
    voter = ConsensusVoter(
        validator=validator,
        executor=executor,
        total_budget_seconds=0.00001,
    )

    candidates = [
        "SELECT username FROM users;",
        "SELECT username FROM users;",
    ]
    # Sleep to ensure budget is already exceeded
    time.sleep(0.001)
    result = voter.select_best_candidate(test_db, candidates)

    assert result.fallback_to_greedy
    assert result.consensus_score == "0/2"
