import sqlite3
import time
from pathlib import Path

import pytest

from src.t2s.safety.executor import SafeSQLExecutor
from src.t2s.safety.validator import SQLValidator


@pytest.fixture
def resource_test_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "resource_fixture.sqlite"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    cur.execute("CREATE TABLE t1 (id INT PRIMARY KEY, val TEXT, num INT);")
    cur.execute("CREATE TABLE t2 (id INT PRIMARY KEY, val TEXT, num INT);")
    cur.execute("CREATE TABLE t3 (id INT PRIMARY KEY, val TEXT, num INT);")

    # Insert 1,000 rows into each of the 3 tables
    rows = [(i, f"val_{i}", i * 10) for i in range(1000)]
    cur.executemany("INSERT INTO t1 VALUES (?, ?, ?);", rows)
    cur.executemany("INSERT INTO t2 VALUES (?, ?, ?);", rows)
    cur.executemany("INSERT INTO t3 VALUES (?, ?, ?);", rows)

    conn.commit()
    conn.close()
    return db_file


def test_resource_timeout_interruption_at_3s(resource_test_db: Path):
    """Assert query defeating row cap via count(*) is interrupted at ~3s (+/-0.5s) and DB remains usable."""
    executor = SafeSQLExecutor(timeout_seconds=3.0, max_rows=100)
    validator = SQLValidator()

    # Query: 3-join cross product wrapped in count(*) passes validator (joins <= 4)
    # 1,000 * 1,000 * 1,000 = 1,000,000,000 rows, defeated row limit by aggregating with count(*)
    heavy_sql = "SELECT count(*) FROM t1 JOIN t2 ON 1=1 JOIN t3 ON 1=1 WHERE t1.val LIKE '%val%';"

    verdict = validator.validate(heavy_sql)
    assert verdict.allowed, f"Validator unexpectedly blocked: {verdict.reasons}"

    t0 = time.perf_counter()
    res = executor.execute_read_only(str(resource_test_db), verdict.rewritten_sql)
    elapsed = time.perf_counter() - t0

    assert not res.success
    assert "interrupted" in str(res.error).lower() or "abort" in str(res.error).lower()
    # Check that it timed out around ~3s (+/- 0.6s margin for windows scheduling)
    assert 2.5 <= elapsed <= 4.0, f"Elapsed time was {elapsed:.2f}s, expected ~3.0s (+/-0.5s)"

    # Check connection remains usable afterwards
    res_followup = executor.execute_read_only(str(resource_test_db), "SELECT count(*) FROM t1;")
    assert res_followup.success
    assert res_followup.rows == [(1000,)]


def test_recursive_cte_authorizer_behavior(resource_test_db: Path):
    """Test benign small recursive CTE (numbers 1..10) and verify SQLite authorizer denial."""
    executor = SafeSQLExecutor(timeout_seconds=3.0)
    validator = SQLValidator()

    small_cte_sql = "WITH RECURSIVE seq(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM seq WHERE x < 10) SELECT * FROM seq;"
    verdict = validator.validate(small_cte_sql)
    # Validator allows valid SELECT CTE
    assert verdict.allowed

    # Sandbox authorizer intercepts all recursive CTEs (SQLITE_RECURSIVE code 33)
    res = executor.execute_read_only(str(resource_test_db), verdict.rewritten_sql)
    assert not res.success
    assert "not authorized" in str(res.error).lower()


def test_sqlite_connection_limits_and_string_doubling(resource_test_db: Path):
    """Test string doubling query against SQLite connection limits (SQLITE_LIMIT_LENGTH)."""
    executor = SafeSQLExecutor(timeout_seconds=3.0)

    # zeroblob / hex string explosion exceeds SQLITE_LIMIT_LENGTH (10MB)
    oversized_sql = "SELECT hex(zeroblob(6000000));"
    res = executor.execute_read_only(str(resource_test_db), oversized_sql)
    assert not res.success
    assert (
        "too big" in str(res.error).lower()
        or "limit" in str(res.error).lower()
        or "not authorized" in str(res.error).lower()
    )


def test_db_opened_read_only_mode(resource_test_db: Path):
    """Confirm database connection strictly denies write operations at URI and engine level."""
    executor = SafeSQLExecutor(timeout_seconds=3.0)

    write_sql = "UPDATE t1 SET val = 'hacked' WHERE id = 1;"
    res = executor.execute_read_only(str(resource_test_db), write_sql)
    assert not res.success
    assert "read-only" in str(res.error).lower() or "not authorized" in str(res.error).lower()


def test_fail_safe_deny_on_internal_exceptions(resource_test_db: Path, monkeypatch):
    """Confirm validator and sandbox fail safe (deny) when internal exceptions occur."""
    validator = SQLValidator()
    executor = SafeSQLExecutor(timeout_seconds=3.0)

    # 1. Force validator exception
    def broken_internal(*args, **kwargs):
        raise RuntimeError("Simulated internal AST parser crash")

    monkeypatch.setattr(validator, "_validate_internal", broken_internal)
    v_verdict = validator.validate("SELECT * FROM t1;")
    assert not v_verdict.allowed
    assert "fail-safe deny" in v_verdict.reasons[0]

    # 2. Force sandbox internal exception
    def broken_connect(*args, **kwargs):
        raise RuntimeError("Simulated driver failure")

    monkeypatch.setattr(sqlite3, "connect", broken_connect)
    e_res = executor.execute_read_only(str(resource_test_db), "SELECT * FROM t1;")
    assert not e_res.success
    assert "Execution error" in str(e_res.error)
