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


def test_validator_allows_quoted_keywords_as_identifiers():
    """Verify quoted, bracketed, and backticked identifiers matching keywords are allowed."""
    validator = SQLValidator()

    res_double_quote = validator.validate('SELECT x AS "update" FROM accounts;')
    assert res_double_quote.allowed is True, f"Blocked: {res_double_quote.reasons}"

    res_bracket = validator.validate("SELECT [delete] FROM inventory;")
    assert res_bracket.allowed is True, f"Blocked: {res_bracket.reasons}"

    res_backtick = validator.validate("SELECT `insert`, name FROM accounts;")
    assert res_backtick.allowed is True, f"Blocked: {res_backtick.reasons}"


def test_validator_allows_string_literals_containing_dml():
    """Verify string literals containing DROP or DELETE are not falsely blocked."""
    validator = SQLValidator()

    res_drop = validator.validate("SELECT title FROM books WHERE summary = 'DROP ALL PREJUDICE';")
    assert res_drop.allowed is True, f"Blocked: {res_drop.reasons}"

    res_delete = validator.validate("SELECT memo FROM notes WHERE content = 'DELETE INACTIVE';")
    assert res_delete.allowed is True, f"Blocked: {res_delete.reasons}"


def test_validator_blocks_comments_containing_dml():
    """Verify comments containing DML are strictly rejected."""
    validator = SQLValidator()

    res_block = validator.validate("SELECT * FROM users /* DROP TABLE users */ WHERE id = 1;")
    assert res_block.allowed is False
    assert any("comments" in r.lower() for r in res_block.reasons)

    res_line = validator.validate("SELECT * FROM users -- DELETE FROM users\nWHERE id = 1;")
    assert res_line.allowed is False
    assert any("comments" in r.lower() for r in res_line.reasons)
