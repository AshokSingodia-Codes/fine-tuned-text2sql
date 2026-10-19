"""SQL Safety Policy data structures and loader."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Set

import yaml


@dataclass
class SafetyPolicy:
    allowed_statements: Set[str] = field(default_factory=lambda: {"SELECT", "WITH"})
    table_allowlist: Set[str] = field(default_factory=set)
    allowed_functions: Set[str] = field(
        default_factory=lambda: {
            "count",
            "avg",
            "sum",
            "min",
            "max",
            "total",
            "abs",
            "round",
            "length",
            "lower",
            "upper",
            "trim",
            "ltrim",
            "rtrim",
            "substr",
            "substring",
            "replace",
            "coalesce",
            "nullif",
            "iif",
            "instr",
            "like",
            "glob",
            "date",
            "time",
            "datetime",
            "julianday",
            "strftime",
            "row_number",
            "rank",
            "dense_rank",
            "ntile",
            "lag",
            "lead",
            "first_value",
            "last_value",
        }
    )
    denied_functions: Set[str] = field(
        default_factory=lambda: {
            "load_extension",
            "fts3_tokenizer",
            "readfile",
            "writefile",
            "edit",
            "zeroblob",
            "randomblob",
            "unhex",
            "random",
            "eval",
            "char",
            "hex",
            "benchmark",
            "sleep",
            "repeat",
            "quote",
        }
    )
    denied_columns: Set[str] = field(
        default_factory=lambda: {
            "password",
            "password_hash",
            "ssn",
            "secret",
            "secret_key",
            "token",
            "api_token",
            "credit_card",
            "credit_card_num",
            "private_key",
            "pin",
        }
    )
    denied_tables: Set[str] = field(
        default_factory=lambda: {
            "sqlite_master",
            "sqlite_schema",
            "sqlite_temp_master",
            "sqlite_sequence",
            "sqlite_stat1",
            "sqlite_stat4",
            "system_user",
            "pg_catalog",
            "information_schema",
        }
    )
    max_row_limit: int = 100
    max_query_length: int = 2000
    max_ast_depth: int = 15
    max_joins_per_branch: int = 4
    max_total_joins: int = 6
    max_subqueries: int = 4
    timeout_seconds: float = 3.0

    @property
    def max_joins(self) -> int:
        return self.max_joins_per_branch

    @property
    def column_denylist(self) -> Set[str]:
        return self.denied_columns

    @property
    def blocked_functions(self) -> Set[str]:
        return self.denied_functions

    @property
    def max_statement_length(self) -> int:
        return self.max_query_length

    @classmethod
    def load(cls, path: Optional[str] = None) -> "SafetyPolicy":
        candidate_paths = [
            path,
            "config/security_policy.yaml",
            "configs/security_policy.yaml",
            "configs/policy.yaml",
        ]

        target_file = None
        for cand in candidate_paths:
            if cand and Path(cand).exists():
                target_file = Path(cand)
                break

        if target_file is None:
            return cls()

        with open(target_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Function allowlist
        raw_allowed_funcs = data.get("allowed_functions") or []
        allowed_funcs = (
            {f.lower() for f in raw_allowed_funcs} if raw_allowed_funcs else cls().allowed_functions
        )

        # Merge function denials
        raw_funcs = data.get("blocked_functions") or data.get("denied_functions") or []
        funcs = {f.lower() for f in raw_funcs} if raw_funcs else cls().denied_functions

        # Merge column denials
        raw_cols = data.get("column_denylist") or data.get("denied_columns") or []
        cols = {c.lower() for c in raw_cols} if raw_cols else cls().denied_columns

        # Merge table denials
        raw_tables = data.get("denied_tables") or []
        tables = {t.lower() for t in raw_tables} if raw_tables else cls().denied_tables

        # Table allowlist
        raw_allow_tables = data.get("table_allowlist") or []
        table_allowlist = {t.lower() for t in raw_allow_tables}

        # Length limit
        max_len = data.get("max_statement_length") or data.get("max_query_length") or 2000

        # Joins
        joins_per_branch = data.get("max_joins_per_branch") or data.get("max_joins") or 4
        total_joins = data.get("max_total_joins") or 6

        return cls(
            allowed_statements=set(data.get("allowed_statements", ["SELECT", "WITH"])),
            table_allowlist=table_allowlist,
            allowed_functions=allowed_funcs,
            denied_functions=funcs,
            denied_columns=cols,
            denied_tables=tables,
            max_row_limit=int(data.get("max_row_limit", 100)),
            max_query_length=int(max_len),
            max_ast_depth=int(data.get("max_ast_depth", 15)),
            max_joins_per_branch=int(joins_per_branch),
            max_total_joins=int(total_joins),
            max_subqueries=int(data.get("max_subqueries", 4)),
            timeout_seconds=float(data.get("timeout_seconds", 3.0)),
        )
