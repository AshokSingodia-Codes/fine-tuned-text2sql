"""Test bootstrap confidence interval and McNemar test."""

from src.t2s.eval.stats import bootstrap_confidence_interval, mcnemar_test


def test_bootstrap_confidence_interval() -> None:
    results = [True] * 80 + [False] * 20  # 80% accuracy
    mean_acc, low, high = bootstrap_confidence_interval(results, seed=42)

    assert abs(mean_acc - 0.80) < 1e-5
    assert 0.70 <= low <= 0.80
    assert 0.80 <= high <= 0.90


def test_mcnemar_test_different_systems() -> None:
    sys_a = [True] * 70 + [False] * 30
    sys_b = [True] * 90 + [False] * 10

    res = mcnemar_test(sys_a, sys_b)

    assert res["c_a_wrong_b_correct"] > res["b_a_correct_b_wrong"]
    assert res["significant"] is True
    assert res["p_value"] < 0.05
