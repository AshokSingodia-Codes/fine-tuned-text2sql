"""Consensus voting module for candidate query selection.

Design Requirements:
- S3. Voting:
  1. Validate ALL N candidates before executing any.
  2. Per-candidate timeout and total request time budget.
  3. Cap on concurrent sandbox executions.
  4. Normalize result sets exactly as eval_spider.py does (compare_query_results logic).
  5. A candidate that fails validation can never win.
  6. Tie-break per PLAN.md: majority count -> lowest execution latency -> shortest SQL.
  7. Fall back to greedy (candidate 0) if all candidates fail.
"""

import json
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.t2s.safety.executor import ExecutionResult, SafeSQLExecutor
from src.t2s.safety.policy import SafetyPolicy
from src.t2s.safety.validator import SQLValidator, ValidationVerdict


def normalize_rows_for_voting(
    rows: Optional[List[Tuple[Any, ...]]], is_order_sensitive: bool = False
) -> str:
    """Normalize query results for hashing and majority grouping, matching eval_spider.py."""
    if rows is None:
        return "__EXEC_FAILED__"
    if is_order_sensitive:
        return json.dumps([list(r) for r in rows], default=str)
    try:
        # Sort rows to achieve multiset equality
        sorted_rows = sorted([tuple(str(x) for x in r) for r in rows])
        return json.dumps(sorted_rows)
    except Exception:
        c = Counter(str(r) for r in rows)
        return json.dumps(sorted(c.items()))


@dataclass
class CandidateEvaluation:
    index: int
    sql: str
    verdict: ValidationVerdict
    exec_res: Optional[ExecutionResult] = None
    exec_latency_ms: float = 0.0
    result_key: Optional[str] = None
    valid: bool = False


@dataclass
class VotingResult:
    winner_sql: str
    winner_verdict: ValidationVerdict
    winner_exec_res: Optional[ExecutionResult]
    consensus_score: str
    winner_index: int
    candidates: List[CandidateEvaluation]
    fallback_to_greedy: bool = False


class ConsensusVoter:
    def __init__(
        self,
        validator: Optional[SQLValidator] = None,
        executor: Optional[SafeSQLExecutor] = None,
        per_candidate_timeout_seconds: float = 3.0,
        total_budget_seconds: float = 15.0,
        max_concurrent: int = 4,
    ) -> None:
        self.validator = validator or SQLValidator(SafetyPolicy.load())
        self.executor = executor or SafeSQLExecutor()
        self.per_candidate_timeout = per_candidate_timeout_seconds
        self.total_budget = total_budget_seconds
        self.max_concurrent = max_concurrent

    def select_best_candidate(
        self,
        db_path: str,
        candidate_sqls: List[str],
        gold_order_sensitive: bool = False,
    ) -> VotingResult:
        """Run candidate validation, sandboxed execution, and majority consensus."""
        if not candidate_sqls:
            empty_verdict = ValidationVerdict(allowed=False, reasons=["No candidates provided"])
            return VotingResult(
                winner_sql="",
                winner_verdict=empty_verdict,
                winner_exec_res=None,
                consensus_score="0/0",
                winner_index=-1,
                candidates=[],
                fallback_to_greedy=True,
            )

        start_time = time.perf_counter()
        n = len(candidate_sqls)
        evaluations: List[CandidateEvaluation] = []

        # 1. Validate ALL N candidates before executing any
        for idx, raw_sql in enumerate(candidate_sqls):
            clean_sql = raw_sql.strip()
            if ";" in clean_sql:
                clean_sql = clean_sql.split(";")[0] + ";"
            verdict = self.validator.validate(clean_sql)
            evaluations.append(
                CandidateEvaluation(
                    index=idx,
                    sql=clean_sql,
                    verdict=verdict,
                    valid=verdict.allowed,
                )
            )

        # 2. Execute validated candidates within time budget
        for cand in evaluations:
            # Check total request time budget
            elapsed = time.perf_counter() - start_time
            if elapsed >= self.total_budget:
                cand.valid = False
                cand.exec_res = ExecutionResult(
                    success=False,
                    columns=[],
                    rows=[],
                    row_count=0,
                    error=f"Total request budget exceeded ({elapsed:.2f}s >= {self.total_budget}s)",
                )
                continue

            if not cand.verdict.allowed:
                # Candidate fails validation -> can NEVER win or be executed
                continue

            sql_to_run = cand.verdict.rewritten_sql or cand.sql
            is_order_sensitive = gold_order_sensitive or ("ORDER BY" in cand.sql.upper())

            t_exec0 = time.perf_counter()
            exec_res = self.executor.execute_read_only(db_path, sql_to_run, canonical_only=False)
            t_exec_ms = (time.perf_counter() - t_exec0) * 1000.0

            cand.exec_res = exec_res
            cand.exec_latency_ms = t_exec_ms

            if exec_res.success:
                cand.result_key = normalize_rows_for_voting(
                    exec_res.rows, is_order_sensitive=is_order_sensitive
                )
            else:
                cand.valid = False

        # 3. Filter successful, valid candidates
        valid_candidates = [c for c in evaluations if c.valid and c.exec_res and c.exec_res.success]

        if not valid_candidates:
            # Fall back to greedy candidate 0
            greedy = evaluations[0]
            return VotingResult(
                winner_sql=greedy.sql,
                winner_verdict=greedy.verdict,
                winner_exec_res=greedy.exec_res,
                consensus_score=f"0/{n}",
                winner_index=0,
                candidates=evaluations,
                fallback_to_greedy=True,
            )

        # 4. Group by normalized result key
        groups: Dict[str, List[CandidateEvaluation]] = {}
        for c in valid_candidates:
            rk = c.result_key or "__EMPTY__"
            if rk not in groups:
                groups[rk] = []
            groups[rk].append(c)

        # 5. Tie-break per PLAN.md:
        # Primary: majority count (descending)
        # Secondary: lowest execution latency (ascending)
        # Tertiary: shortest SQL length (ascending)
        sorted_groups = sorted(
            groups.values(),
            key=lambda grp: (
                -len(grp),  # Most votes
                min(c.exec_latency_ms for c in grp),  # Lowest latency
                min(len(c.sql) for c in grp),  # Shortest SQL
            ),
        )

        winning_group = sorted_groups[0]
        # Pick best candidate in winning group
        winner = sorted(
            winning_group,
            key=lambda c: (c.exec_latency_ms, len(c.sql)),
        )[0]

        votes = len(winning_group)
        score = f"{votes}/{n}"

        return VotingResult(
            winner_sql=winner.sql,
            winner_verdict=winner.verdict,
            winner_exec_res=winner.exec_res,
            consensus_score=score,
            winner_index=winner.index,
            candidates=evaluations,
            fallback_to_greedy=False,
        )
