"""Unit tests for Safe read-only SQLite Executor."""

import sqlite3
import tempfile
from pathlib import Path

from src.t2s.safety.executor import SafeSQLExecutor


def test_executor_read_only_select():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INT, name TEXT);")
    conn.execute("INSERT INTO users VALUES (1, 'Alice'), (2, 'Bob');")
    conn.commit()
    conn.close()

    executor = SafeSQLExecutor(timeout_seconds=2.0, max_rows=10)
    res = executor.execute_read_only(db_path, "SELECT * FROM users ORDER BY id;")

    assert res.success is True
    assert res.columns == ["id", "name"]
    assert res.row_count == 2
    assert res.rows == [(1, "Alice"), (2, "Bob")]

    Path(db_path).unlink(missing_ok=True)


def test_executor_blocks_write_attempt():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INT, name TEXT);")
    conn.commit()
    conn.close()

    executor = SafeSQLExecutor()
    res = executor.execute_read_only(db_path, "INSERT INTO users VALUES (3, 'Eve');")

    assert res.success is False
    assert "error" in str(res.error).lower()

    Path(db_path).unlink(missing_ok=True)
