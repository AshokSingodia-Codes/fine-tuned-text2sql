"""SQL Safety Policy data structures and loader."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

import yaml


@dataclass
class SafetyPolicy:
    allowed_statements: Set[str] = field(default_factory=lambda: {"SELECT", "WITH"})
    denied_functions: Set[str] = field(
        default_factory=lambda: {
            "load_extension",
            "eval",
            "randomblob",
            "char",
            "hex",
        }
    )
    denied_columns: Set[str] = field(
        default_factory=lambda: {"password", "ssn", "secret", "token", "credit_card"}
    )
    denied_tables: Set[str] = field(
        default_factory=lambda: {
            "sqlite_master",
            "sqlite_schema",
            "sqlite_temp_master",
            "sqlite_sequence",
            "system_user",
        }
    )
    max_row_limit: int = 100
    max_query_length: int = 2000
    max_joins: int = 5
    max_subqueries: int = 4
    timeout_seconds: float = 3.0

    @classmethod
    def load(cls, path: Optional[str] = None) -> "SafetyPolicy":
        if path is None:
            path = "configs/policy.yaml"

        p = Path(path)
        if not p.exists():
            return cls()

        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls(
            allowed_statements=set(data.get("allowed_statements", ["SELECT", "WITH"])),
            denied_functions=set(data.get("denied_functions", [])),
            denied_columns=set(data.get("denied_columns", [])),
            denied_tables=set(data.get("denied_tables", [])),
            max_row_limit=data.get("max_row_limit", 100),
            max_query_length=data.get("max_query_length", 2000),
            max_joins=data.get("max_joins", 5),
            max_subqueries=data.get("max_subqueries", 4),
            timeout_seconds=float(data.get("timeout_seconds", 3.0)),
        )
