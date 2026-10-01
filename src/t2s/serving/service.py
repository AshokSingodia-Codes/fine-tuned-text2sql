"""Service orchestration for text-to-SQL query processing with Consensus Voting and Self-Correction."""

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from src.t2s.data.prompts import build_prompt_messages
from src.t2s.gen.backends import BaseBackend, get_backend
from src.t2s.safety.executor import SafeSQLExecutor
from src.t2s.safety.policy import SafetyPolicy
from src.t2s.safety.validator import SQLValidator
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
        try:
            self.backend = get_backend(backend_name, model_name=model_path)
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

        # 4. AST Validation
        t2 = time.perf_counter()
        verdict = self.validator.validate(clean_sql)
        timings["validation_ms"] = round((time.perf_counter() - t2) * 1000.0, 2)

        if not verdict.allowed:
            return {
                "request_id": request_id,
                "db_id": db_id,
                "question": question,
                "sql": clean_sql,
                "allowed": False,
                "reasons": verdict.reasons,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "truncated": False,
                "retried": False,
                "consensus_score": "1/1",
                "timings_ms": timings,
                "model_version": "Qwen2.5-Coder-3B-QLoRA",
            }

        # 5. Read-Only Execution
        t3 = time.perf_counter()
        db_path = self.db_registry.get_db_path(db_id)
        exec_res = self.executor.execute_read_only(str(db_path), verdict.rewritten_sql)
        timings["execution_ms"] = round((time.perf_counter() - t3) * 1000.0, 2)

        retried = False
        # Execution-guided retry on SQL runtime error
        if not exec_res.success and exec_res.error:
            retried = True
            retry_prompt = prompt_msgs + [
                {"role": "assistant", "content": clean_sql},
                {"role": "user", "content": f"The query failed with error: {exec_res.error}. Please fix the SQL query."},
            ]
            t_retry = time.perf_counter()
            retry_gen = self.backend.generate([retry_prompt])[0]
            retry_sql = retry_gen.get("text", "").strip() if isinstance(retry_gen, dict) else str(retry_gen)
            if ";" in retry_sql:
                retry_sql = retry_sql.split(";")[0] + ";"

            retry_verdict = self.validator.validate(retry_sql)
            if retry_verdict.allowed:
                clean_sql = retry_sql
                exec_res = self.executor.execute_read_only(str(db_path), retry_verdict.rewritten_sql)
            timings["retry_ms"] = round((time.perf_counter() - t_retry) * 1000.0, 2)

        timings["total_ms"] = round((time.perf_counter() - start_time) * 1000.0, 2)

        return {
            "request_id": request_id,
            "db_id": db_id,
            "question": question,
            "sql": clean_sql,
            "allowed": True,
            "reasons": verdict.reasons,
            "columns": exec_res.columns,
            "rows": [list(row) for row in exec_res.rows],
            "row_count": exec_res.row_count,
            "truncated": exec_res.truncated,
            "retried": retried,
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

        successful_candidates: List[Dict[str, Any]] = []
        blocked_reasons: List[str] = []

        t_exec = time.perf_counter()
        for idx, out in enumerate(gen_outputs):
            raw_sql = out.get("text", "") if isinstance(out, dict) else str(out)
            clean_sql = raw_sql.strip()
            if ";" in clean_sql:
                clean_sql = clean_sql.split(";")[0] + ";"

            verdict = self.validator.validate(clean_sql)
            if not verdict.allowed:
                blocked_reasons.extend(verdict.reasons)
                continue

            exec_res = self.executor.execute_read_only(db_path, verdict.rewritten_sql)
            retried = False

            # Self-correction on execution runtime error
            if not exec_res.success and exec_res.error:
                retried = True
                retry_prompt = prompt_msgs + [
                    {"role": "assistant", "content": clean_sql},
                    {"role": "user", "content": f"The SQL query failed with SQLite error: {exec_res.error}. Please correct the query syntax or column names."},
                ]
                retry_out = self.backend.generate([retry_prompt])[0]
                retry_sql = retry_out.get("text", "").strip() if isinstance(retry_out, dict) else str(retry_out)
                if ";" in retry_sql:
                    retry_sql = retry_sql.split(";")[0] + ";"

                retry_verdict = self.validator.validate(retry_sql)
                if retry_verdict.allowed:
                    clean_sql = retry_sql
                    exec_res = self.executor.execute_read_only(db_path, retry_verdict.rewritten_sql)

            if exec_res.success:
                rows_tuple = tuple(sorted([tuple(r) for r in exec_res.rows]))
                successful_candidates.append(
                    {
                        "candidate_idx": idx,
                        "sql": clean_sql,
                        "rewritten_sql": verdict.rewritten_sql,
                        "columns": exec_res.columns,
                        "rows": exec_res.rows,
                        "row_count": exec_res.row_count,
                        "truncated": exec_res.truncated,
                        "retried": retried,
                        "result_key": json.dumps(rows_tuple, default=str),
                    }
                )

        timings["validation_execution_ms"] = round((time.perf_counter() - t_exec) * 1000.0, 2)

        # Handle case where all candidates failed or were blocked
        if not successful_candidates:
            timings["total_ms"] = round((time.perf_counter() - start_time) * 1000.0, 2)
            return {
                "request_id": request_id,
                "db_id": db_id,
                "question": question,
                "sql": "-- All candidates blocked or failed execution",
                "allowed": False,
                "reasons": list(set(blocked_reasons)) or ["Execution failed across all candidate queries"],
                "columns": [],
                "rows": [],
                "row_count": 0,
                "truncated": False,
                "retried": True,
                "consensus_score": f"0/{n_samples}",
                "timings_ms": timings,
                "model_version": "Qwen2.5-Coder-3B-QLoRA",
            }

        # Step 4: Majority Voting across execution result keys
        result_groups: Dict[str, List[Dict[str, Any]]] = {}
        for cand in successful_candidates:
            rk = cand["result_key"]
            if rk not in result_groups:
                result_groups[rk] = []
            result_groups[rk].append(cand)

        # Sort groups by count descending
        sorted_groups = sorted(result_groups.values(), key=lambda g: len(g), reverse=True)
        winning_group = sorted_groups[0]
        winner = winning_group[0]
        votes = len(winning_group)

        timings["total_ms"] = round((time.perf_counter() - start_time) * 1000.0, 2)

        return {
            "request_id": request_id,
            "db_id": db_id,
            "question": question,
            "sql": winner["sql"],
            "allowed": True,
            "reasons": [],
            "columns": winner["columns"],
            "rows": [list(r) for r in winner["rows"]],
            "row_count": winner["row_count"],
            "truncated": winner["truncated"],
            "retried": winner["retried"],
            "consensus_score": f"{votes}/{n_samples}",
            "timings_ms": timings,
            "model_version": "Qwen2.5-Coder-3B-QLoRA",
        }
