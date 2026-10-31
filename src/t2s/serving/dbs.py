"""Database registry for demo SQLite databases."""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.t2s.data.schema import get_sqlite_schema_ddl


class DatabaseRegistry:
    def __init__(self, db_base_dir: str = "data/raw/spider/database") -> None:
        self.db_base_dir = Path(db_base_dir)
        self._upload_dirs: list[Path] = []  # user-uploaded db directories

    def register_upload_dir(self, upload_dir: str) -> None:
        """Register an additional directory that contains user-uploaded .sqlite files."""
        p = Path(upload_dir)
        if p not in self._upload_dirs:
            self._upload_dirs.append(p)

    def get_db_info_from_path(self, db_path: str, db_id: str) -> dict:
        """Return db info dict directly from an absolute path (for uploads)."""
        tables: list[str] = []
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r[0] for r in cursor.fetchall() if not r[0].startswith("sqlite_")]
            conn.close()
        except Exception:
            tables = []
        p = Path(db_path)
        size_bytes = p.stat().st_size if p.exists() else 0
        return {
            "db_id": db_id,
            "table_count": len(tables),
            "tables": tables,
            "size_bytes": size_bytes,
            "source": "uploaded",
        }

    def list_databases(self) -> List[Dict[str, Any]]:
        seen_dbs = set()
        dbs = []

        if self.db_base_dir.exists():
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

        # Check user-uploaded databases
        for upload_dir in self._upload_dirs:
            for p in sorted(upload_dir.glob("*.sqlite")):
                db_id = p.stem
                if db_id not in seen_dbs:
                    info = self.get_db_info_from_path(str(p), db_id)
                    seen_dbs.add(db_id)
                    dbs.append(info)

        # Fallback to committed seed databases in db/seeds/ if not found
        seeds_dir = Path("db/seeds")
        if seeds_dir.exists():
            for p in sorted(seeds_dir.glob("*.sqlite")):
                db_id = p.stem
                # Support chinook_1 alias for chinook.sqlite
                alias_ids = [db_id]
                if db_id == "chinook":
                    alias_ids.append("chinook_1")
                for aid in alias_ids:
                    if aid not in seen_dbs:
                        info = self.get_db_info_from_path(str(p), aid)
                        seen_dbs.add(aid)
                        dbs.append(info)

        return dbs

    def get_db_path(self, db_id: str) -> Optional[Path]:
        # Path traversal guard
        if not db_id or ".." in db_id or "/" in db_id or "\\" in db_id:
            return None

        import os

        if os.getenv("APP_PROFILE", "").lower() == "demo":
            allowed_demo_dbs = os.getenv("DEMO_DB_ALLOWLIST", "chinook_1").split(",")
            if db_id not in [d.strip() for d in allowed_demo_dbs if d.strip()]:
                # Also allow user-uploaded databases in demo mode
                for upload_dir in self._upload_dirs:
                    p = (upload_dir / f"{db_id}.sqlite").resolve()
                    if p.exists() and upload_dir.resolve() in p.parents:
                        return p
                return None

        p = (self.db_base_dir / f"{db_id}.sqlite").resolve()
        base_resolved = self.db_base_dir.resolve()
        if p.exists() and base_resolved in p.parents:
            return p
        p_sub = (self.db_base_dir / db_id / f"{db_id}.sqlite").resolve()
        if p_sub.exists() and base_resolved in p_sub.parents:
            return p_sub

        # Check upload dirs
        for upload_dir in self._upload_dirs:
            pu = (upload_dir / f"{db_id}.sqlite").resolve()
            if pu.exists() and upload_dir.resolve() in pu.parents:
                return pu

        # Fallback to committed seed databases in db/seeds/
        seeds_dir = Path("db/seeds")
        if seeds_dir.exists():
            ps = (seeds_dir / f"{db_id}.sqlite").resolve()
            if ps.exists() and seeds_dir.resolve() in ps.parents:
                return ps
            if db_id == "chinook_1":
                ps_chinook = (seeds_dir / "chinook.sqlite").resolve()
                if ps_chinook.exists() and seeds_dir.resolve() in ps_chinook.parents:
                    return ps_chinook
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

        size_bytes = db_path.stat().st_size if db_path.exists() else 0
        return {
            "db_id": db_id,
            "table_count": len(tables),
            "tables": tables,
            "size_bytes": size_bytes,
            "source": "builtin",
        }

    def get_schema_ddl(self, db_id: str, include_sample_rows: bool = False) -> str:
        db_path = self.get_db_path(db_id)
        if not db_path:
            raise FileNotFoundError(f"Database '{db_id}' not found")
        return get_sqlite_schema_ddl(str(db_path), include_sample_rows=include_sample_rows)
