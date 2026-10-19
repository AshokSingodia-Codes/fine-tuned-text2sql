"""Safe SQLite Read-Only Executor with authorizer callback and execution timeout."""

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Tuple

import sqlglot

from src.t2s.safety.policy import SafetyPolicy


@dataclass
class ExecutionResult:
    success: bool
    columns: List[str] = field(default_factory=list)
    rows: List[Tuple[Any, ...]] = field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    truncated: bool = False
    error: Optional[str] = None


def _sqlite_authorizer(
    action_code: int, arg1: Any, arg2: Any, db_name: Any, trigger_name: Any
) -> int:
    """Authorizer callback for SQLite connection level defense."""
    # SQLITE_OK = 0, SQLITE_DENY = 1, SQLITE_IGNORE = 2
    # Allowed actions for read-only query execution
    allowed_codes = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
    }

    if action_code in allowed_codes:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


class SafeSQLExecutor:
    def __init__(
        self,
        timeout_seconds: float = 3.0,
        max_rows: int = 100,
        policy: Optional[SafetyPolicy] = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_rows = max_rows
        self.policy = policy or SafetyPolicy.load()

    def execute_read_only(
        self,
        db_path: str,
        sql: str,
        canonical_only: bool = True,
    ) -> ExecutionResult:
        p = Path(db_path)
        if not p.exists():
            return ExecutionResult(success=False, error=f"Database file does not exist: {db_path}")

        # Task D2.a: Execute canonical re-serialized SQL from sqlglot, never unparsed raw strings
        exec_sql = sql
        if canonical_only and sql and sql.strip():
            try:
                parsed = sqlglot.parse_one(sql.strip().rstrip(";"), read="sqlite")
                exec_sql = parsed.sql(dialect="sqlite")
                if not exec_sql.endswith(";"):
                    exec_sql += ";"
            except Exception as e:
                return ExecutionResult(success=False, error=f"Canonical SQL formatting error: {e}")

        # Connect strictly in read-only mode using URI syntax
        uri_path = f"file:{p.resolve().as_posix()}?mode=ro"

        start_time = time.perf_counter()
        conn = None
        try:
            conn = sqlite3.connect(uri_path, uri=True, timeout=self.timeout_seconds)

            # Defensive engine configs (Task D2.e)
            if hasattr(conn, "enable_load_extension"):
                try:
                    conn.enable_load_extension(False)
                except Exception:
                    pass

            for cfg_name, cfg_val in [
                ("SQLITE_DBCONFIG_DEFENSIVE", True),
                ("SQLITE_DBCONFIG_ENABLE_FTS3_TOKENIZER", False),
                ("SQLITE_DBCONFIG_TRUSTED_SCHEMA", False),
            ]:
                if hasattr(sqlite3, cfg_name) and hasattr(conn, "setconfig"):
                    try:
                        conn.setconfig(getattr(sqlite3, cfg_name), cfg_val)
                    except Exception:
                        pass

            # Enforce read-only at connection PRAGMA level
            conn.execute("PRAGMA query_only = ON;")

            # Authorizer as ground truth (Task D2.c)
            denied_tbls = {t.lower() for t in self.policy.denied_tables}
            denied_cols = {c.lower() for c in self.policy.denied_columns}
            allowed_funcs = {f.lower() for f in self.policy.allowed_functions}
            denied_funcs = {f.lower() for f in self.policy.denied_functions}

            def authorizer_callback(
                action_code: int, arg1: Any, arg2: Any, db_name: Any, trigger_name: Any
            ) -> int:
                # Disallow PRAGMA (19) and ATTACH (24)
                if action_code in (
                    getattr(sqlite3, "SQLITE_PRAGMA", 19),
                    getattr(sqlite3, "SQLITE_ATTACH", 24),
                    getattr(sqlite3, "SQLITE_DETACH", 25),
                ):
                    return sqlite3.SQLITE_DENY

                # Allow SELECT root actions
                if action_code == sqlite3.SQLITE_SELECT:
                    return sqlite3.SQLITE_OK

                # Check table/column reads (SQLITE_READ = 20)
                if action_code == sqlite3.SQLITE_READ:
                    tbl = str(arg1).lower() if arg1 else ""
                    col = str(arg2).lower() if arg2 else ""

                    if tbl in denied_tbls:
                        return sqlite3.SQLITE_DENY
                    if col in denied_cols:
                        return sqlite3.SQLITE_DENY
                    for dc in denied_cols:
                        if col == dc or col.startswith(f"{dc}_") or col.endswith(f"_{dc}"):
                            return sqlite3.SQLITE_DENY
                    return sqlite3.SQLITE_OK

                # Check function execution (SQLITE_FUNCTION = 31)
                if action_code == sqlite3.SQLITE_FUNCTION:
                    fn_name = str(arg2).lower() if arg2 else ""
                    if denied_funcs and fn_name in denied_funcs:
                        return sqlite3.SQLITE_DENY
                    if allowed_funcs and fn_name not in allowed_funcs:
                        return sqlite3.SQLITE_DENY
                    return sqlite3.SQLITE_OK

                # Deny all other actions (DML, DDL, recursive CTEs, etc.)
                return sqlite3.SQLITE_DENY

            conn.set_authorizer(authorizer_callback)

            # Set defensive connection limits
            for limit_name, limit_val in [
                ("SQLITE_LIMIT_LENGTH", 10_000_000),  # 10 MB maximum string / blob length
                ("SQLITE_LIMIT_SQL_LENGTH", 100_000),  # 100 KB max SQL length
                ("SQLITE_LIMIT_EXPR_DEPTH", 200),  # Max expression tree depth
                ("SQLITE_LIMIT_COMPOUND_SELECT", 50),  # Max compound SELECT terms
            ]:
                if hasattr(sqlite3, limit_name) and hasattr(conn, "setlimit"):
                    try:
                        conn.setlimit(getattr(sqlite3, limit_name), limit_val)
                    except Exception:
                        pass

            # Install progress handler for query execution timeout control
            start_ticks = time.perf_counter()
            timeout_sec = self.timeout_seconds

            def progress_callback() -> int:
                if (time.perf_counter() - start_ticks) > timeout_sec:
                    return 1  # Non-zero returns abort query
                return 0

            conn.set_progress_handler(progress_callback, 100)

            cursor = conn.cursor()
            cursor.execute(exec_sql)

            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            fetched_rows = cursor.fetchmany(self.max_rows + 1)

            truncated = False
            if len(fetched_rows) > self.max_rows:
                truncated = True
                rows = fetched_rows[: self.max_rows]
            else:
                rows = fetched_rows

            exec_time = (time.perf_counter() - start_time) * 1000.0

            return ExecutionResult(
                success=True,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_time_ms=round(exec_time, 2),
                truncated=truncated,
                error=None,
            )
        except sqlite3.DatabaseError as e:
            exec_time = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                success=False,
                execution_time_ms=round(exec_time, 2),
                error=f"SQLite Security/Execution error: {e}",
            )
        except Exception as e:
            exec_time = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                success=False,
                execution_time_ms=round(exec_time, 2),
                error=f"Execution error: {e}",
            )
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
