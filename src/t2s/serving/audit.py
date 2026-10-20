"""Audit logger for recording text-to-SQL API requests and safety verdicts."""

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional


class AuditLogger:
    def __init__(self, db_path: Optional[str] = None) -> None:
        target_path = db_path or os.getenv("AUDIT_DB_PATH", "reports/audit_log.db")
        self.db_path = Path(target_path)
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
        except (PermissionError, OSError):
            # Fallback for read-only containers / Hugging Face Spaces
            fallback_dir = Path("/tmp") if Path("/tmp").exists() else Path.home()
            self.db_path = fallback_dir / "audit_log.db"
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                request_id TEXT PRIMARY KEY,
                timestamp REAL,
                api_key_hash TEXT,
                db_id TEXT,
                question TEXT,
                generated_sql TEXT,
                allowed INTEGER,
                reasons TEXT,
                row_count INTEGER,
                retried INTEGER,
                execution_time_ms REAL,
                model_version TEXT
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_feedback (
                request_id TEXT PRIMARY KEY,
                timestamp REAL,
                rating INTEGER,
                comment TEXT
            );
            """
        )
        conn.commit()
        conn.close()

    def log_query(
        self,
        request_id: str,
        api_key: str,
        db_id: str,
        question: str,
        generated_sql: str,
        allowed: bool,
        reasons: list,
        row_count: int,
        retried: bool,
        execution_time_ms: float,
        model_version: str = "Qwen2.5-Coder-3B-QLoRA",
    ) -> None:
        api_key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
        # Redaction: truncate question and record hash to prevent credential leakage in logs
        sanitized_question = (question[:97] + "...") if len(question) > 100 else question
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO audit_logs (
                request_id, timestamp, api_key_hash, db_id, question,
                generated_sql, allowed, reasons, row_count, retried,
                execution_time_ms, model_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                request_id,
                time.time(),
                api_key_hash,
                db_id,
                sanitized_question,
                generated_sql,
                1 if allowed else 0,
                json.dumps(reasons),
                row_count,
                1 if retried else 0,
                execution_time_ms,
                model_version,
            ),
        )
        conn.commit()
        conn.close()

    def log_feedback(self, request_id: str, rating: int, comment: Optional[str] = None) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO user_feedback (request_id, timestamp, rating, comment)
            VALUES (?, ?, ?, ?);
            """,
            (request_id, time.time(), rating, comment or ""),
        )
        conn.commit()
        conn.close()


default_audit_logger = AuditLogger()
