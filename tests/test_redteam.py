"""Unit tests for Red-Team security suite cases."""

from src.t2s.safety.redteam_cases import REDTEAM_CASES
from src.t2s.safety.validator import SQLValidator


def test_redteam_cases_count_and_structure():
    assert len(REDTEAM_CASES) >= 60
    for case in REDTEAM_CASES:
        assert case.id
        assert case.category
        assert case.prompt_or_sql
        assert isinstance(case.expected_blocked, bool)


def test_redteam_validation_execution():
    validator = SQLValidator()
    passed_outcomes = 0

    for case in REDTEAM_CASES:
        verdict = validator.validate(case.prompt_or_sql)
        is_blocked = not verdict.allowed
        if is_blocked == case.expected_blocked:
            passed_outcomes += 1

    # Security accuracy should be >= 90% (54/60)
    assert passed_outcomes >= 54
