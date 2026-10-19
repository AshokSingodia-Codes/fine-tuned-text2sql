"""Unit tests for config/security_policy.yaml rules and enforcement."""

from src.t2s.safety.policy import SafetyPolicy
from src.t2s.safety.validator import SQLValidator


def test_policy_load_from_config():
    policy = SafetyPolicy.load("config/security_policy.yaml")
    assert "password" in policy.column_denylist
    assert "load_extension" in policy.blocked_functions
    assert "sqlite_master" in policy.denied_tables
    assert policy.max_statement_length == 2000
    assert policy.max_ast_depth == 15
    assert policy.max_joins_per_branch == 4
    assert policy.max_total_joins == 6


def test_rule_table_allowlist():
    policy = SafetyPolicy(table_allowlist={"users", "orders"})
    validator = SQLValidator(policy)

    allowed_v = validator.validate("SELECT * FROM users JOIN orders ON users.id = orders.user_id;")
    assert allowed_v.allowed

    blocked_v = validator.validate("SELECT * FROM employees;")
    assert not blocked_v.allowed
    assert any("not in the allowed database schema" in r for r in blocked_v.reasons)


def test_rule_column_denylist():
    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)

    for col in ["password", "password_hash", "ssn", "secret", "token", "credit_card", "pin"]:
        v = validator.validate(f"SELECT {col} FROM accounts;")
        assert not v.allowed
        assert any("sensitive column" in r for r in v.reasons)


def test_rule_blocked_functions():
    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)

    for fn in [
        "load_extension('lib.so')",
        "randomblob(100)",
        "char(65)",
        "hex('abc')",
        "zeroblob(50)",
    ]:
        v = validator.validate(f"SELECT {fn};")
        assert not v.allowed
        assert any("denied by policy" in r for r in v.reasons)


def test_rule_max_statement_length():
    policy = SafetyPolicy(max_query_length=50)
    validator = SQLValidator(policy)

    long_query = "SELECT * FROM users WHERE " + " AND ".join([f"col{i} = {i}" for i in range(20)])
    v = validator.validate(long_query)
    assert not v.allowed
    assert any("exceeds max length" in r for r in v.reasons)


def test_rule_max_ast_depth():
    policy = SafetyPolicy(max_ast_depth=5)
    validator = SQLValidator(policy)

    # Deeply nested subquery exceeding depth 5
    deep_query = "SELECT * FROM t1 WHERE c1 IN (SELECT c2 FROM t2 WHERE c2 IN (SELECT c3 FROM t3 WHERE c3 IN (SELECT c4 FROM t4 WHERE c4 IN (SELECT c5 FROM t5))));"
    v = validator.validate(deep_query)
    assert not v.allowed
    assert any("AST depth exceeds max allowed limit" in r for r in v.reasons)


def test_rule_denied_tables():
    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)

    for tbl in ["sqlite_master", "sqlite_schema", "sqlite_sequence", "sqlite_temp_master"]:
        v = validator.validate(f"SELECT * FROM {tbl};")
        assert not v.allowed
        assert any("denied system/sensitive table" in r for r in v.reasons)


def test_rule_allowed_statements():
    policy = SafetyPolicy.load("config/security_policy.yaml")
    validator = SQLValidator(policy)

    for stmt in [
        "DROP TABLE singer;",
        "DELETE FROM users;",
        "UPDATE accounts SET balance = 0;",
        "INSERT INTO t VALUES (1);",
    ]:
        v = validator.validate(stmt)
        assert not v.allowed
