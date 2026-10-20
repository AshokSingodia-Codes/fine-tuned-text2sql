"""Database registry for demo SQLite databases."""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.t2s.data.schema import get_sqlite_schema_ddl


class DatabaseRegistry:
    def __init__(self, db_base_dir: str = "data/raw/spider/database") -> None:
        self.db_base_dir = Path(db_base_dir)

    def list_databases(self) -> List[Dict[str, Any]]:
        if not self.db_base_dir.exists():
            return []

        seen_dbs = set()
        dbs = []

        # Check nested subdirectories (e.g. data/raw/spider/database/<db_id>/<db_id>.sqlite)
        for p in sorted(self.db_base_dir.glob("*/*.sqlite")):
            db_id = p.parent.name
            if db_id not in seen_dbs:
                info = self.get_db_info(db_id)
                if info is not None:
                    seen_dbs.add(db_id)
                    dbs.append(info)

        # Check flat files (e.g. data/raw/spider/database/<db_id>.sqlite)
        for p in sorted(self.db_base_dir.glob("*.sqlite")):
            db_id = p.stem
            if db_id not in seen_dbs:
                info = self.get_db_info(db_id)
                if info is not None:
                    seen_dbs.add(db_id)
                    dbs.append(info)

        return dbs

    def get_db_path(self, db_id: str) -> Optional[Path]:
        # Path traversal guard: db_id must be safe identifier without directory separators or traversal
        if not db_id or ".." in db_id or "/" in db_id or "\\" in db_id:
            return None

        # Enforce demo profile allowlist if configured (demo: chinook_1 only)
        import os

        if os.getenv("APP_PROFILE", "").lower() == "demo":
            allowed_demo_dbs = os.getenv("DEMO_DB_ALLOWLIST", "chinook_1").split(",")
            if db_id not in [d.strip() for d in allowed_demo_dbs if d.strip()]:
                return None

        p = (self.db_base_dir / f"{db_id}.sqlite").resolve()
        base_resolved = self.db_base_dir.resolve()

        if p.exists() and base_resolved in p.parents:
            return p

        # Check subdirectories
        p_sub = (self.db_base_dir / db_id / f"{db_id}.sqlite").resolve()
        if p_sub.exists() and base_resolved in p_sub.parents:
            return p_sub
        return None

    def get_db_info(self, db_id: str) -> Optional[Dict[str, Any]]:
        db_path = self.get_db_path(db_id)
        if not db_path:
            return None

        tables = []
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]
            conn.close()
        except Exception:
            tables = []

        return {
            "db_id": db_id,
            "table_count": len(tables),
            "tables": tables,
        }

    def get_schema_ddl(self, db_id: str, include_sample_rows: bool = False) -> str:
        db_path = self.get_db_path(db_id)
        if not db_path:
            raise FileNotFoundError(f"Database '{db_id}' not found")
        return get_sqlite_schema_ddl(str(db_path), include_sample_rows=include_sample_rows)
