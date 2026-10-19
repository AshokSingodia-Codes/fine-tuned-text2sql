"""SQL AST Validator using sqlglot for safe text-to-SQL execution."""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set

import sqlglot
from sqlglot import exp
from sqlglot.tokens import TokenType

from src.t2s.safety.policy import SafetyPolicy


@dataclass
class ValidationVerdict:
    allowed: bool
    reasons: List[str] = field(default_factory=list)
    rewritten_sql: str = ""


def _compute_ast_depth(node: exp.Expression) -> int:
    """Recursively calculate the maximum depth of an AST expression."""
    max_child_depth = 0
    for child in node.iter_expressions():
        d = _compute_ast_depth(child)
        if d > max_child_depth:
            max_child_depth = d
    return 1 + max_child_depth


class SQLValidator:
    def __init__(self, policy: Optional[SafetyPolicy] = None) -> None:
        self.policy = policy or SafetyPolicy.load()

    def validate(
        self,
        sql: str,
        allowed_tables: Optional[Set[str]] = None,
        allowed_columns: Optional[Set[str]] = None,
    ) -> ValidationVerdict:
        try:
            return self._validate_internal(
                sql=sql, allowed_tables=allowed_tables, allowed_columns=allowed_columns
            )
        except Exception as e:
            # Fail-safe (deny) on any unexpected internal error or exception
            return ValidationVerdict(
                allowed=False,
                reasons=[f"Validator internal error (fail-safe deny): {e}"],
                rewritten_sql="",
            )

    def _validate_internal(
        self,
        sql: str,
        allowed_tables: Optional[Set[str]] = None,
        allowed_columns: Optional[Set[str]] = None,
    ) -> ValidationVerdict:
        reasons: List[str] = []

        if not sql or not sql.strip():
            return ValidationVerdict(allowed=False, reasons=["Empty SQL query"], rewritten_sql="")

        raw_sql = sql.strip()

        # 1. Check max query length
        if len(raw_sql) > self.policy.max_query_length:
            return ValidationVerdict(
                allowed=False,
                reasons=[f"SQL query exceeds max length of {self.policy.max_query_length}"],
                rewritten_sql="",
            )

        # 2. Input character policy before parsing: reject control characters and non-ASCII whitespace outside literals
        non_literal_sql = re.sub(r"'[^']*'", "''", raw_sql)
        for ch in non_literal_sql:
            code = ord(ch)
            if (code < 32 and ch not in ("\t", "\n", "\r")) or code == 127:
                reasons.append(f"Forbidden control character detected: 0x{code:02x}")
                break
            elif code > 127 and (
                ch.isspace()
                or "\u2000" <= ch <= "\u200f"
                or ch in ("\xa0", "\ufeff", "\u2028", "\u2029", "\u3000")
            ):
                reasons.append(
                    f"Forbidden non-ASCII whitespace or format character detected: U+{code:04X}"
                )
                break
        try:
            tokens = sqlglot.tokenize(raw_sql, read="sqlite")
            for t in tokens:
                if (
                    t.comments
                    or t.token_type in (TokenType.COMMENT, TokenType.HINT)
                    or "COMMENT" in t.token_type.name
                ):
                    reasons.append("SQL comments are not allowed")
                    break
        except Exception:
            # Fallback if tokenizer fails: check for raw comment symbols
            if "--" in raw_sql or "/*" in raw_sql:
                reasons.append("SQL comments are not allowed")

        # 3. Check for multiple statements
        clean_stmt = raw_sql.rstrip(";").strip()
        try:
            stmts = sqlglot.parse(clean_stmt, read="sqlite")
            if len(stmts) > 1:
                reasons.append("Multiple SQL statements are strictly forbidden")
        except Exception:
            pass

        # Fallback check for semicolon outside strings
        if ";" in clean_stmt:
            stripped_strings = re.sub(r"'[^']*'", "''", clean_stmt)
            stripped_strings = re.sub(r'"[^"]*"', '""', stripped_strings)
            if ";" in stripped_strings:
                reasons.append("Multiple SQL statements are strictly forbidden")

        # 4. Parse AST with sqlglot
        try:
            parsed = sqlglot.parse_one(clean_stmt, read="sqlite")
        except Exception as e:
            reasons.append(f"SQL parsing error: {e}")
            return ValidationVerdict(allowed=False, reasons=reasons, rewritten_sql="")

        if parsed is None:
            reasons.append("Invalid or unparseable SQL AST")
            return ValidationVerdict(allowed=False, reasons=reasons, rewritten_sql="")

        # 5. Check root node type (must be Select, Union, Intersect, or Except)
        if not isinstance(parsed, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
            reasons.append(
                f"Root query type '{parsed.key}' is not allowed (must be SELECT/UNION/INTERSECT/EXCEPT)"
            )

        # 6. Check for forbidden AST expression nodes anywhere in tree (pure AST decision)
        forbidden_expr_types = (
            exp.Drop,
            exp.Delete,
            exp.Insert,
            exp.Update,
            exp.Alter,
            exp.Create,
            exp.Command,
            exp.Pragma,
        )
        for expr in parsed.find_all(forbidden_expr_types):
            reasons.append(f"Forbidden statement/keyword detected: {expr.key.upper()}")

        # 7. Check max AST depth
        ast_depth = _compute_ast_depth(parsed)
        if ast_depth > self.policy.max_ast_depth:
            reasons.append(
                f"Query AST depth exceeds max allowed limit ({ast_depth} > {self.policy.max_ast_depth})"
            )

        # 8. Walk AST for table references
        active_allowlist = allowed_tables or self.policy.table_allowlist
        tables_found = set()
        for table in parsed.find_all(exp.Table):
            t_name = table.name.lower()
            tables_found.add(t_name)
            if t_name in self.policy.denied_tables:
                reasons.append(f"Access to denied system/sensitive table '{t_name}' is blocked")
            if active_allowlist and t_name not in {t.lower() for t in active_allowlist}:
                reasons.append(f"Table '{t_name}' is not in the allowed database schema")

        # 9. Walk AST for column references
        for col in parsed.find_all(exp.Column):
            c_name = col.name.lower()
            if c_name in self.policy.denied_columns:
                reasons.append(f"Access to denied sensitive column '{c_name}' is blocked")
            for dc in self.policy.denied_columns:
                if c_name == dc or c_name.startswith(f"{dc}_") or c_name.endswith(f"_{dc}"):
                    msg = f"Access to denied sensitive column '{c_name}' is blocked"
                    if msg not in reasons:
                        reasons.append(msg)

        # 10. Walk AST for functions (enforce function allowlist + denylist)
        allowed_funcs = {f.lower() for f in self.policy.allowed_functions}
        for func in parsed.find_all(exp.Expression):
            if isinstance(func, (exp.Anonymous, exp.Func)) and not isinstance(
                func, (exp.And, exp.Or, exp.Not, exp.Binary, exp.Connector, exp.Case, exp.If)
            ):
                if isinstance(func, exp.Anonymous):
                    f_name = (
                        func.this.name.lower()
                        if hasattr(func.this, "name")
                        else str(func.this).lower()
                    )
                else:
                    f_name = func.key.lower()

                if allowed_funcs and f_name not in allowed_funcs:
                    reasons.append(f"Function '{f_name}' is not in the allowed functions policy")
                if f_name in self.policy.denied_functions:
                    reasons.append(f"Execution of function '{f_name}' is denied by policy")

        for df in self.policy.denied_functions:
            if re.search(r"\b" + re.escape(df) + r"\s*\(", clean_stmt, re.IGNORECASE):
                msg = f"Execution of function '{df}' is denied by policy"
                if msg not in reasons:
                    reasons.append(msg)

        # 11. Check join complexity limits (per branch and total)
        total_joins = len(list(parsed.find_all(exp.Join)))
        if total_joins > self.policy.max_total_joins:
            reasons.append(
                f"Query exceeds max total joins ({total_joins} > {self.policy.max_total_joins})"
            )

        for select_branch in parsed.find_all(exp.Select):
            joins = list(select_branch.find_all(exp.Join))
            tables = list(select_branch.find_all(exp.Table))
            branch_joins = max(len(joins), max(0, len(tables) - 1))
            if branch_joins > self.policy.max_joins_per_branch:
                reasons.append(
                    f"Query exceeds max allowed joins ({branch_joins} > {self.policy.max_joins_per_branch})"
                )

        # 12. Enforce max_row_limit
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

        unique_reasons = []
        for r in reasons:
            if r not in unique_reasons:
                unique_reasons.append(r)

        allowed = len(unique_reasons) == 0
        return ValidationVerdict(
            allowed=allowed, reasons=unique_reasons, rewritten_sql=rewritten_sql if allowed else ""
        )
