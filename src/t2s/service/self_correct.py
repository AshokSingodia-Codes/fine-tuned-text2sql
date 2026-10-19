"""Self-correction service module for execution/syntax error repair.

Design Requirements:
- S1. Retry ONLY on execution or syntax errors (no such column/table, syntax error, timeout)
  or parse failures.
- NEVER retry after a policy block (denied table/column/function, DML, stacked statements,
  recursive CTEs, etc.): doing so gives an attacker an oracle.
- Never put validator rule text in a repair prompt.
- Quote the DB error as data, truncated to at most 300 characters.
- Max 2 retries (total up to 3 attempts: initial + 2 retries).
- Every retried SQL MUST go through the full validator and sandbox again.
- API attempts array is client-facing and sanitized:
  status in {ok, exec_error:<category>, blocked_by_policy} with NO rule names or policy details.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.t2s.safety.executor import ExecutionResult, SafeSQLExecutor
from src.t2s.safety.policy import SafetyPolicy
from src.t2s.safety.validator import SQLValidator, ValidationVerdict


def categorize_db_error(error_msg: Optional[str]) -> str:
    """Categorize execution/database error for client-facing sanitized status."""
    if not error_msg:
        return "unknown"
    err_lower = error_msg.lower()
    if "no such table" in err_lower:
        return "no_such_table"
    elif "no such column" in err_lower:
        return "no_such_column"
    elif "syntax error" in err_lower or "near " in err_lower:
        return "syntax_error"
    elif "timed out" in err_lower or "interrupted" in err_lower:
        return "timeout"
    elif "ambiguous column" in err_lower:
        return "ambiguous_column"
    elif "misuse" in err_lower:
        return "aggregate_misuse"
    elif "type" in err_lower or "decode" in err_lower:
        return "type_or_decode_error"
    else:
        return "runtime_error"


def sanitize_attempt_status(
    allowed: bool,
    exec_success: bool,
    error_msg: Optional[str] = None,
) -> str:
    """Map internal state to client-facing sanitized status string."""
    if not allowed:
        return "blocked_by_policy"
    if exec_success:
        return "ok"
    cat = categorize_db_error(error_msg)
    return f"exec_error:{cat}"


@dataclass
class AttemptRecord:
    attempt_index: int
    sql: str
    status: str
    allowed: bool
    audit_reasons: List[str] = field(default_factory=list)
    db_error: Optional[str] = None


@dataclass
class SelfCorrectionResult:
    final_sql: str
    allowed: bool
    verdict: ValidationVerdict
    exec_res: Optional[ExecutionResult]
    attempts: List[AttemptRecord]
    retried: bool = False


class SelfCorrectionRunner:
    def __init__(
        self,
        validator: Optional[SQLValidator] = None,
        executor: Optional[SafeSQLExecutor] = None,
        max_retries: int = 2,
    ) -> None:
        self.validator = validator or SQLValidator(SafetyPolicy.load())
        self.executor = executor or SafeSQLExecutor()
        self.max_retries = max(0, min(max_retries, 5))

    def run(
        self,
        db_path: str,
        initial_sql: str,
        generate_fn: Callable[[List[Dict[str, str]]], str],
        base_prompt_messages: List[Dict[str, str]],
        audit_log_fn: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> SelfCorrectionResult:
        """Execute query with execution-guided self-correction loop.

        CRITICAL SECURITY INVARIANT:
        If validator blocks initial or retried SQL, STOP IMMEDIATELY.
        NEVER feed policy block reasons or retry on policy blocks.
        """
        current_sql = initial_sql.strip()

        attempts: List[AttemptRecord] = []
        retried = False

        for attempt_idx in range(self.max_retries + 1):
            # 1. Full AST Validation
            verdict = self.validator.validate(current_sql)

            # Audit logging
            if audit_log_fn:
                audit_log_fn(
                    {
                        "attempt": attempt_idx,
                        "sql": current_sql,
                        "allowed": verdict.allowed,
                        "reasons": verdict.reasons,
                    }
                )

            # If blocked by policy: STOP IMMEDIATELY
            if not verdict.allowed:
                status = "blocked_by_policy"
                attempts.append(
                    AttemptRecord(
                        attempt_index=attempt_idx,
                        sql=current_sql,
                        status=status,
                        allowed=False,
                        audit_reasons=verdict.reasons,
                        db_error=None,
                    )
                )
                return SelfCorrectionResult(
                    final_sql=current_sql,
                    allowed=False,
                    verdict=verdict,
                    exec_res=None,
                    attempts=attempts,
                    retried=retried,
                )

            # 2. Execute validated canonical SQL in sandbox
            sql_to_run = verdict.rewritten_sql or current_sql
            exec_res = self.executor.execute_read_only(db_path, sql_to_run)

            if exec_res.success:
                status = "ok"
                attempts.append(
                    AttemptRecord(
                        attempt_index=attempt_idx,
                        sql=current_sql,
                        status=status,
                        allowed=True,
                        audit_reasons=[],
                        db_error=None,
                    )
                )
                return SelfCorrectionResult(
                    final_sql=current_sql,
                    allowed=True,
                    verdict=verdict,
                    exec_res=exec_res,
                    attempts=attempts,
                    retried=retried,
                )

            # 3. Execution failure occurred (e.g. no such column, syntax error)
            db_err = exec_res.error or "Unknown database error"
            status = sanitize_attempt_status(True, False, db_err)
            attempts.append(
                AttemptRecord(
                    attempt_index=attempt_idx,
                    sql=current_sql,
                    status=status,
                    allowed=True,
                    audit_reasons=[],
                    db_error=db_err,
                )
            )

            # If max retries reached, exit loop
            if attempt_idx >= self.max_retries:
                break

            # 4. Build repair prompt:
            # - Quote the DB error as data, truncate to 300 chars
            # - Never include policy text or rule names
            retried = True
            safe_error_quote = re.sub(r"[\r\n]+", " ", db_err)[:300]
            repair_user_msg = (
                f'The previous query resulted in database execution error:\n"{safe_error_quote}"\n'
                f"Please fix the error and provide the corrected SQL query."
            )

            repair_messages = list(base_prompt_messages) + [
                {"role": "assistant", "content": current_sql},
                {"role": "user", "content": repair_user_msg},
            ]

            # 5. Generate repair candidate
            new_sql_raw = generate_fn(repair_messages)
            new_sql = new_sql_raw.strip() if new_sql_raw else ""
            if ";" in new_sql:
                new_sql = new_sql.split(";")[0] + ";"
            current_sql = new_sql

        # Reached after max retries exhausted with failure
        return SelfCorrectionResult(
            final_sql=current_sql,
            allowed=True,
            verdict=verdict,
            exec_res=exec_res,
            attempts=attempts,
            retried=retried,
        )
