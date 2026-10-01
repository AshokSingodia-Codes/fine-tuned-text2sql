"""SQL AST Validator using sqlglot for safe text-to-SQL execution."""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set

import sqlglot
from sqlglot import exp
from src.t2s.safety.policy import SafetyPolicy


@dataclass
class ValidationVerdict:
    allowed: bool
    reasons: List[str] = field(default_factory=list)
    rewritten_sql: str = ""


class SQLValidator:
    def __init__(self, policy: Optional[SafetyPolicy] = None) -> None:
        self.policy = policy or SafetyPolicy.load()

    def validate(
        self,
        sql: str,
        allowed_tables: Optional[Set[str]] = None,
        allowed_columns: Optional[Set[str]] = None,
    ) -> ValidationVerdict:
        reasons: List[str] = []

        if not sql or not sql.strip():
            return ValidationVerdict(allowed=False, reasons=["Empty SQL query"], rewritten_sql="")

        raw_sql = sql.strip()

        # 1. Check max length
        if len(raw_sql) > self.policy.max_query_length:
            return ValidationVerdict(
                allowed=False,
                reasons=[f"SQL query exceeds max length of {self.policy.max_query_length}"],
                rewritten_sql="",
            )

        # 2. Check comment smuggling
        if "--" in raw_sql or "/*" in raw_sql:
            reasons.append("SQL comments are not allowed")

        # 3. Check multiple statements
        # Split statements ignoring trailing semicolon
        clean_stmt = raw_sql.rstrip(";").strip()
        if ";" in clean_stmt:
            reasons.append("Multiple SQL statements are strictly forbidden")

        # 4. Check dangerous keywords before parsing
        forbidden_keywords = [
            "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
            "ATTACH", "DETACH", "PRAGMA", "VACUUM", "REPLACE", "TRUNCATE",
            "EXEC", "EXECUTE", "LOAD_EXTENSION"
        ]
        tokens_upper = re.findall(r"\b[A-Z_]+\b", clean_stmt.upper())
        for kw in forbidden_keywords:
            if kw in tokens_upper:
                reasons.append(f"Forbidden statement/keyword detected: {kw}")

        # 5. Parse AST with sqlglot
        try:
            parsed = sqlglot.parse_one(clean_stmt, read="sqlite")
        except Exception as e:
            reasons.append(f"SQL parsing error: {e}")
            return ValidationVerdict(allowed=False, reasons=reasons, rewritten_sql="")

        if parsed is None:
            reasons.append("Invalid or unparseable SQL AST")
            return ValidationVerdict(allowed=False, reasons=reasons, rewritten_sql="")

        # 6. Check root node type (must be Select, Union, Intersect, or Except)
        if not isinstance(parsed, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
            reasons.append(f"Root query type '{parsed.key}' is not allowed (must be SELECT/UNION/INTERSECT/EXCEPT)")

        # 7. Walk AST for table references
        tables_found = set()
        for table in parsed.find_all(exp.Table):
            t_name = table.name.lower()
            tables_found.add(t_name)
            if t_name in self.policy.denied_tables:
                reasons.append(f"Access to denied system/sensitive table '{t_name}' is blocked")
            if allowed_tables is not None and t_name not in {t.lower() for t in allowed_tables}:
                reasons.append(f"Table '{t_name}' is not in the allowed database schema")

        # 8. Walk AST for column references
        for col in parsed.find_all(exp.Column):
            c_name = col.name.lower()
            if c_name in self.policy.denied_columns:
                reasons.append(f"Access to denied sensitive column '{c_name}' is blocked")

        # 9. Walk AST for functions (checking exp.Func and Anonymous functions)
        for func in parsed.find_all(exp.Func, exp.Anonymous):
            if isinstance(func, exp.Anonymous):
                f_name = func.this.name.lower() if hasattr(func.this, "name") else str(func.this).lower()
            else:
                f_name = func.key.lower()
            if f_name in self.policy.denied_functions:
                reasons.append(f"Execution of function '{f_name}' is denied by policy")

        # Also regex fallback for denied functions in raw query
        for df in self.policy.denied_functions:
            if re.search(r"\b" + re.escape(df) + r"\s*\(", clean_stmt, re.IGNORECASE):
                reasons.append(f"Execution of function '{df}' is denied by policy")

        # 10. Check join complexity limit (counting explicit JOINs and FROM table lists)
        n_explicit_joins = len(list(parsed.find_all(exp.Join)))
        n_tables = len(list(parsed.find_all(exp.Table)))
        effective_joins = max(n_explicit_joins, max(0, n_tables - 1))
        if effective_joins > self.policy.max_joins:
            reasons.append(f"Query exceeds max allowed joins ({effective_joins} > {self.policy.max_joins})")

        # 11. Enforce max_row_limit
        rewritten_sql = clean_stmt
        if isinstance(parsed, exp.Select):
            limit_exp = parsed.args.get("limit")
            if limit_exp is None:
                parsed = parsed.limit(self.policy.max_row_limit)
            else:
                try:
                    curr_limit = int(limit_exp.expression.this)
                    if curr_limit > self.policy.max_row_limit:
                        parsed = parsed.limit(self.policy.max_row_limit)
                except Exception:
                    parsed = parsed.limit(self.policy.max_row_limit)
            rewritten_sql = parsed.sql(dialect="sqlite")

        if not rewritten_sql.endswith(";"):
            rewritten_sql += ";"

        allowed = len(reasons) == 0
        return ValidationVerdict(allowed=allowed, reasons=reasons, rewritten_sql=rewritten_sql if allowed else "")
