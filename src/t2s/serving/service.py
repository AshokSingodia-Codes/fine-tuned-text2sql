"""Service orchestration for text-to-SQL query processing with Consensus Voting and Self-Correction."""

import time
import uuid
from typing import Any, Dict, List

from src.t2s.data.prompts import build_prompt_messages
from src.t2s.gen.backends import get_backend
from src.t2s.safety.executor import SafeSQLExecutor
from src.t2s.safety.policy import SafetyPolicy
from src.t2s.safety.validator import SQLValidator
from src.t2s.service.self_correct import SelfCorrectionRunner
from src.t2s.service.voting import ConsensusVoter
from src.t2s.serving.dbs import DatabaseRegistry


class Text2SQLService:
    def __init__(
        self,
        backend_name: str = "mock",
        model_path: str = "models/qlora_adapter",
        db_base_dir: str = "data/raw/spider/database",
    ) -> None:
        self.db_registry = DatabaseRegistry(db_base_dir=db_base_dir)
        self.policy = SafetyPolicy.load()
        self.validator = SQLValidator(self.policy)
        self.executor = SafeSQLExecutor(
            timeout_seconds=self.policy.timeout_seconds,
            max_rows=self.policy.max_row_limit,
        )
        self.self_corrector = SelfCorrectionRunner(
            validator=self.validator,
            executor=self.executor,
            max_retries=2,
        )
        self.consensus_voter = ConsensusVoter(
            validator=self.validator,
            executor=self.executor,
            per_candidate_timeout_seconds=self.policy.timeout_seconds,
            total_budget_seconds=15.0,
            max_concurrent=4,
        )
        try:
            self.backend = get_backend(backend_name, model_name=model_path, model_path=model_path)
        except Exception:
            self.backend = get_backend("mock")

    def process_query(
        self,
        db_id: str,
        question: str,
        include_sample_rows: bool = False,
        enable_consensus: bool = True,
        n_samples: int = 5,
    ) -> Dict[str, Any]:
        if enable_consensus and n_samples > 1:
            return self.process_query_consensus(
                db_id=db_id,
                question=question,
                include_sample_rows=include_sample_rows,
                n_samples=n_samples,
            )

        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        timings: Dict[str, float] = {}

        # 1. Fetch schema DDL
        t0 = time.perf_counter()
        schema_ddl = self.db_registry.get_schema_ddl(db_id, include_sample_rows=include_sample_rows)
        timings["schema_fetch_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)

        # 2. Build prompt
        prompt_msgs = build_prompt_messages(schema_ddl, question)

        # 3. Model inference
        t1 = time.perf_counter()
        gen_output = self.backend.generate([prompt_msgs])[0]
        timings["inference_ms"] = round((time.perf_counter() - t1) * 1000.0, 2)

        raw_sql = gen_output.get("text", "") if isinstance(gen_output, dict) else str(gen_output)
        clean_sql = raw_sql.strip()
        if ";" in clean_sql:
            clean_sql = clean_sql.split(";")[0] + ";"

        db_path = str(self.db_registry.get_db_path(db_id))

        def generate_repair(msgs: List[Dict[str, str]]) -> str:
            res = self.backend.generate([msgs])[0]
            return res.get("text", "") if isinstance(res, dict) else str(res)

        t_corr = time.perf_counter()
        corr_res = self.self_corrector.run(
            db_path=db_path,
            initial_sql=clean_sql,
            generate_fn=generate_repair,
            base_prompt_messages=prompt_msgs,
        )
        timings["self_correction_ms"] = round((time.perf_counter() - t_corr) * 1000.0, 2)
        timings["total_ms"] = round((time.perf_counter() - start_time) * 1000.0, 2)

        client_attempts = [
            {"attempt_index": att.attempt_index, "sql": att.sql, "status": att.status}
            for att in corr_res.attempts
        ]

        if not corr_res.allowed:
            return {
                "request_id": request_id,
                "db_id": db_id,
                "question": question,
                "sql": corr_res.final_sql,
                "allowed": False,
                "reasons": corr_res.verdict.reasons,
                "attempts": client_attempts,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "truncated": False,
                "retried": corr_res.retried,
                "consensus_score": "1/1",
                "timings_ms": timings,
                "model_version": "Qwen2.5-Coder-3B-QLoRA",
            }

        exec_res = corr_res.exec_res
        columns = exec_res.columns if exec_res else []
        rows = [list(r) for r in exec_res.rows] if exec_res else []
        row_count = exec_res.row_count if exec_res else 0
        truncated = exec_res.truncated if exec_res else False

        return {
            "request_id": request_id,
            "db_id": db_id,
            "question": question,
            "sql": corr_res.final_sql,
            "allowed": True,
            "reasons": corr_res.verdict.reasons,
            "attempts": client_attempts,
            "columns": columns,
            "rows": rows,
            "row_count": row_count,
            "truncated": truncated,
            "retried": corr_res.retried,
            "consensus_score": "1/1",
            "timings_ms": timings,
            "model_version": "Qwen2.5-Coder-3B-QLoRA",
        }

    def process_query_consensus(
        self,
        db_id: str,
        question: str,
        include_sample_rows: bool = False,
        n_samples: int = 5,
    ) -> Dict[str, Any]:
        """Execution-Guided Self-Correction with Majority Voting (Consensus Decoding)."""
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()
        timings: Dict[str, float] = {}

        t0 = time.perf_counter()
        schema_ddl = self.db_registry.get_schema_ddl(db_id, include_sample_rows=include_sample_rows)
        timings["schema_fetch_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)

        prompt_msgs = build_prompt_messages(schema_ddl, question)
        prompt_list = [prompt_msgs] * n_samples

        t1 = time.perf_counter()
        gen_outputs = self.backend.generate(prompt_list)
        timings["inference_ms"] = round((time.perf_counter() - t1) * 1000.0, 2)

        db_path = str(self.db_registry.get_db_path(db_id))

        candidate_sqls = []
        for out in gen_outputs:
            raw_sql = out.get("text", "") if isinstance(out, dict) else str(out)
            candidate_sqls.append(raw_sql)

        t_vote = time.perf_counter()
        vote_res = self.consensus_voter.select_best_candidate(
            db_path=db_path,
            candidate_sqls=candidate_sqls,
        )
        timings["voting_execution_ms"] = round((time.perf_counter() - t_vote) * 1000.0, 2)
        timings["total_ms"] = round((time.perf_counter() - start_time) * 1000.0, 2)

        client_attempts = []
        for c in vote_res.candidates:
            err = c.exec_res.error if c.exec_res and not c.exec_res.success else None
            status = (
                "blocked_by_policy"
                if not c.verdict.allowed
                else (
                    "ok"
                    if c.exec_res and c.exec_res.success
                    else f"exec_error:{c.exec_res.error[:30] if c.exec_res else 'failed'}"
                )
            )
            from src.t2s.service.self_correct import sanitize_attempt_status

            status = sanitize_attempt_status(
                c.verdict.allowed, bool(c.exec_res and c.exec_res.success), err
            )
            client_attempts.append({"attempt_index": c.index, "sql": c.sql, "status": status})

        if not vote_res.winner_verdict.allowed:
            return {
                "request_id": request_id,
                "db_id": db_id,
                "question": question,
                "sql": vote_res.winner_sql,
                "allowed": False,
                "reasons": vote_res.winner_verdict.reasons,
                "attempts": client_attempts,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "truncated": False,
                "retried": False,
                "consensus_score": vote_res.consensus_score,
                "timings_ms": timings,
                "model_version": "Qwen2.5-Coder-3B-QLoRA",
            }

        exec_res = vote_res.winner_exec_res
        columns = exec_res.columns if exec_res else []
        rows = [list(r) for r in exec_res.rows] if exec_res else []
        row_count = exec_res.row_count if exec_res else 0
        truncated = exec_res.truncated if exec_res else False

        return {
            "request_id": request_id,
            "db_id": db_id,
            "question": question,
            "sql": vote_res.winner_sql,
            "allowed": True,
            "reasons": vote_res.winner_verdict.reasons,
            "attempts": client_attempts,
            "columns": columns,
            "rows": rows,
            "row_count": row_count,
            "truncated": truncated,
            "retried": False,
            "consensus_score": vote_res.consensus_score,
            "timings_ms": timings,
            "model_version": "Qwen2.5-Coder-3B-QLoRA",
        }
