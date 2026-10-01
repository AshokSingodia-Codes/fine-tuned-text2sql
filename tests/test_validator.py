"""Unit tests for SQL AST Validator and Policy Enforcement."""

from src.t2s.safety.policy import SafetyPolicy
from src.t2s.safety.validator import SQLValidator


def test_validator_allowed_query():
    policy = SafetyPolicy()
    validator = SQLValidator(policy)

    res = validator.validate("SELECT name, age FROM students WHERE age > 18;")
    assert res.allowed is True
    assert len(res.reasons) == 0
    assert "LIMIT 100" in res.rewritten_sql


def test_validator_blocks_ddl():
    validator = SQLValidator()
    res = validator.validate("DROP TABLE students;")
    assert res.allowed is False
    assert any("DROP" in r for r in res.reasons)


def test_validator_blocks_comment_smuggling():
    validator = SQLValidator()
    res = validator.validate("SELECT * FROM students -- malicious comment;")
    assert res.allowed is False
    assert any("comments" in r.lower() for r in res.reasons)


def test_validator_blocks_multi_statements():
    validator = SQLValidator()
    res = validator.validate("SELECT 1; DELETE FROM students;")
    assert res.allowed is False
    assert any("multiple" in r.lower() for r in res.reasons)


def test_validator_blocks_denied_columns():
    policy = SafetyPolicy(denied_columns={"password", "ssn"})
    validator = SQLValidator(policy)

    res = validator.validate("SELECT id, password FROM users;")
    assert res.allowed is False
    assert any("password" in r for r in res.reasons)


def test_validator_allows_set_operations():
    validator = SQLValidator()
    res_intersect = validator.validate("SELECT id FROM t1 INTERSECT SELECT id FROM t2;")
    assert res_intersect.allowed is True

    res_except = validator.validate("SELECT id FROM t1 EXCEPT SELECT id FROM t2;")
    assert res_except.allowed is True
