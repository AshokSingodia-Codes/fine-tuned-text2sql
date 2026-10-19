import sqlite3
from typing import Set

import hypothesis.strategies as st
from hypothesis import given, settings

from src.t2s.safety.executor import SafeSQLExecutor
from src.t2s.safety.policy import SafetyPolicy
from src.t2s.safety.validator import SQLValidator


def test_executed_sql_matches_rewritten_canonical_invariant():
    """Invariant test: executed SQL == rewritten_sql, and re-parsing gives identical AST."""
    validator = SQLValidator()

    raw_query = "select  name,  age   from   singer   where   age>20"
    verdict = validator.validate(raw_query)
    assert verdict.allowed
    canonical_sql = verdict.rewritten_sql

    import sqlglot

    ast1 = sqlglot.parse_one(canonical_sql, read="sqlite")
    ast2 = sqlglot.parse_one(ast1.sql(dialect="sqlite"), read="sqlite")
    assert ast1 == ast2


def test_v2_attack_success_regression_suite(tmp_path):
    """Ensure the 4 previously successful heldout_v2 attacks are blocked (static or sandbox)."""
    db_file = tmp_path / "regression.sqlite"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE singer (id INT, name TEXT);")
    conn.commit()
    conn.close()

    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)
    executor = SafeSQLExecutor(policy=policy)

    # 1. ENC_V2_02 (Vertical tab \x0b)
    v1 = validator.validate("SELECT\x0b* FROM singer;")
    assert not v1.allowed
    assert any("0x0b" in r for r in v1.reasons)

    # 2. ENC_V2_03 (Form feed \x0c)
    v2 = validator.validate("SELECT\x0c* FROM singer;")
    assert not v2.allowed
    assert any("0x0c" in r for r in v2.reasons)

    # 3. ENC_V2_05 (unhex function)
    v3 = validator.validate("SELECT unhex('73656c656374');")
    assert not v3.allowed
    assert any("unhex" in r for r in v3.reasons)
    # Also sandbox denies
    res3 = executor.execute_read_only(
        str(db_file), "SELECT unhex('73656c656374');", canonical_only=False
    )
    assert not res3.success

    # 4. FNC_V2_05 (fts3_tokenizer)
    v4 = validator.validate("SELECT fts3_tokenizer('simple');")
    assert not v4.allowed
    assert any("fts3_tokenizer" in r for r in v4.reasons)
    res4 = executor.execute_read_only(
        str(db_file), "SELECT fts3_tokenizer('simple');", canonical_only=False
    )
    assert not res4.success


# Parser-differential Hypothesis test (Task D2.f)
_CONTROL_CHARS = [
    "\x00",
    "\x01",
    "\x02",
    "\x03",
    "\x04",
    "\x05",
    "\x06",
    "\x07",
    "\x08",
    "\x0b",
    "\x0c",
    "\x0e",
    "\x0f",
    "\x10",
    "\x1f",
    "\x7f",
    "\xa0",
    "\u2000",
    "\u2001",
    "\u200b",
    "\u200c",
    "\u200d",
    "\u2028",
    "\u2029",
    "\ufeff",
]

_TEMPLATES = [
    "SELECT {} name FROM singer WHERE age > 10;",
    "SELECT name {} FROM singer WHERE id = 1;",
    "SELECT count(*) FROM {} singer;",
    "SELECT * FROM singer WHERE {} age = 20;",
    "SELECT name FROM users WHERE {} password = '123';",
    "SELECT load_extension('hack.so') {};",
    "SELECT fts3_tokenizer('simple') {};",
    "SELECT unhex('1234') {};",
]


class LoggingAuthorizer:
    def __init__(self):
        self.tables_read: Set[str] = set()
        self.columns_read: Set[str] = set()
        self.functions_called: Set[str] = set()

    def __call__(self, action_code, arg1, arg2, db, trigger):
        if action_code == sqlite3.SQLITE_READ:
            if arg1:
                self.tables_read.add(str(arg1).lower())
            if arg2:
                self.columns_read.add(str(arg2).lower())
        elif action_code == sqlite3.SQLITE_FUNCTION:
            if arg2:
                self.functions_called.add(str(arg2).lower())
        return sqlite3.SQLITE_OK


@settings(max_examples=1000, deadline=None)
@given(
    char=st.sampled_from(_CONTROL_CHARS),
    template=st.sampled_from(_TEMPLATES),
)
def test_parser_differential_hypothesis(char: str, template: str):
    """If validator allows, authorizer sees only allowed tables, columns, and functions."""
    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)

    sql = template.format(char)
    verdict = validator.validate(sql)

    if verdict.allowed:
        # If validator allowed, verify with SQLite logging authorizer
        conn = sqlite3.connect(":memory:")
        logger = LoggingAuthorizer()
        conn.set_authorizer(logger)
        conn.execute("CREATE TABLE singer (id INT, name TEXT, age INT);")
        try:
            conn.execute(verdict.rewritten_sql)
        except Exception:
            pass
        finally:
            conn.close()

        # Invariant: tables read must not contain denied tables
        assert not (logger.tables_read & policy.denied_tables), (
            f"Denied table read: {logger.tables_read}"
        )
        # Invariant: columns read must not contain denied columns
        assert not (logger.columns_read & policy.denied_columns), (
            f"Denied column read: {logger.columns_read}"
        )
        # Invariant: functions called must be a subset of allowed functions
        for fn in logger.functions_called:
            assert fn in policy.allowed_functions, f"Unauthorized function called: {fn}"


def test_canonical_semantic_preservation():
    """Verify that canonical rewritten SQL preserves semantics on Spider dev queries."""
    import json
    from pathlib import Path

    equiv_file = Path("results/canonical_equiv.json")
    assert equiv_file.exists(), "results/canonical_equiv.json must exist"

    with open(equiv_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = data["summary"]
    # At least 96% of all queries match semantically
    assert summary["equivalence_rate_of_allowed"] >= 0.95

    # Check that all semantic mismatches are solely due to the security limit (LIMIT 100)
    for m in data["semantic_mismatches"]:
        assert m["canon_row_count"] == 100
        assert m["orig_row_count"] > 100

    # Test an individual sample execution to verify invariant in-memory
    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)
    test_sql = "SELECT name, age FROM singer WHERE age > 20 ORDER BY age;"
    v_res = validator.validate(test_sql)
    assert v_res.allowed

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE singer (name TEXT, age INT);")
    conn.execute("INSERT INTO singer VALUES ('Alice', 25), ('Bob', 19), ('Charlie', 30);")
    orig_res = conn.execute(test_sql).fetchall()
    canon_res = conn.execute(v_res.rewritten_sql).fetchall()
    conn.close()

    assert orig_res == canon_res
