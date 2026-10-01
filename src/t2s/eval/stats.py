"""Statistical confidence intervals and significance testing."""

from typing import Any, Dict, List, Tuple

import numpy as np
from scipy import stats


def bootstrap_confidence_interval(
    results: List[bool],
    confidence_level: float = 0.95,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> Tuple[float, float, float]:
    if not results:
        return 0.0, 0.0, 0.0

    arr = np.array(results, dtype=np.float64)
    original_mean = float(np.mean(arr))

    rng = np.random.default_rng(seed)
    bootstrap_means = []
    n = len(results)

    for _ in range(n_bootstrap):
        sample = rng.choice(arr, size=n, replace=True)
        bootstrap_means.append(np.mean(sample))

    alpha = (1.0 - confidence_level) / 2.0
    low = float(np.percentile(bootstrap_means, alpha * 100))
    high = float(np.percentile(bootstrap_means, (1.0 - alpha) * 100))

    return original_mean, low, high


def mcnemar_test(results_a: List[bool], results_b: List[bool]) -> Dict[str, Any]:
    if len(results_a) != len(results_b):
        raise ValueError(
            f"Results lists must have same length: {len(results_a)} vs {len(results_b)}"
        )

    b = 0
    c = 0
    both_correct = 0
    both_wrong = 0

    for a, b_val in zip(results_a, results_b):
        if a and not b_val:
            b += 1
        elif not a and b_val:
            c += 1
        elif a and b_val:
            both_correct += 1
        else:
            both_wrong += 1

    total_discordant = b + c
    if total_discordant == 0:
        return {
            "statistic": 0.0,
            "p_value": 1.0,
            "significant": False,
            "b_a_correct_b_wrong": b,
            "c_a_wrong_b_correct": c,
        }

    if total_discordant < 25:
        p_val = float(2 * stats.binom.cdf(min(b, c), total_discordant, 0.5))
        p_val = min(1.0, p_val)
        stat = float(abs(b - c))
    else:
        stat = float((abs(b - c) - 1.0) ** 2 / total_discordant)
        p_val = float(1.0 - stats.chi2.cdf(stat, df=1))

    return {
        "statistic": stat,
        "p_value": p_val,
        "significant": p_val < 0.05,
        "b_a_correct_b_wrong": b,
        "c_a_wrong_b_correct": c,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
    }
