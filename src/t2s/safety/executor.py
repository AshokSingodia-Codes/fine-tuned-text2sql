"""Safe SQLite Read-Only Executor with authorizer callback and execution timeout."""

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ExecutionResult:
    success: bool
    columns: List[str] = field(default_factory=list)
    rows: List[Tuple[Any, ...]] = field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    truncated: bool = False
    error: Optional[str] = None


def _sqlite_authorizer(action_code: int, arg1: Any, arg2: Any, db_name: Any, trigger_name: Any) -> int:
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
    def __init__(self, timeout_seconds: float = 3.0, max_rows: int = 100) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_rows = max_rows

    def execute_read_only(
        self,
        db_path: str,
        sql: str,
    ) -> ExecutionResult:
        p = Path(db_path)
        if not p.exists():
            return ExecutionResult(success=False, error=f"Database file does not exist: {db_path}")

        # Connect strictly in read-only mode using URI syntax
        uri_path = f"file:{p.resolve().as_posix()}?mode=ro"

        start_time = time.perf_counter()
        conn = None
        try:
            conn = sqlite3.connect(uri_path, uri=True, timeout=self.timeout_seconds)

            # Enforce read-only at connection PRAGMA level
            conn.execute("PRAGMA query_only = ON;")

            # Install security authorizer
            conn.set_authorizer(_sqlite_authorizer)

            # Install progress handler for query execution timeout control
            start_ticks = time.perf_counter()
            timeout_sec = self.timeout_seconds

            def progress_callback() -> int:
                if (time.perf_counter() - start_ticks) > timeout_sec:
                    return 1  # Non-zero returns abort query
                return 0

            conn.set_progress_handler(progress_callback, 100)

            cursor = conn.cursor()
            cursor.execute(sql)

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
