"""
Module: rate_stats
Layer: evals (utility)
Purpose: Hand-implemented Wilson score confidence interval and pass-rate helpers.
         Uses only `math` — no scipy, sklearn, or statsmodels dependency.
         Named `rate_stats`, not `statistics`: `pyproject.toml` puts `evals/` on
         `pythonpath`, so a module named `statistics` shadows the stdlib module of
         that name for every importer in the process (DEC-162).
Dependencies: math
Used by: evals/case_stats.py, evals/compare.py, evals/refusal_rate.py,
         evals/sequence_runner.py, evals/summary.py.
"""

from __future__ import annotations

import math

Z_95 = 1.96
Z_95_SQ = Z_95 * Z_95  # 3.8416


def wilson_interval(
    successes: int,
    trials: int,
    z: float = Z_95,
) -> tuple[float, float]:
    """Compute the Wilson score confidence interval for a pass rate.

    Args:
        successes: Number of passing trials (0 ≤ successes ≤ trials).
        trials: Total number of trials (must be > 0).
        z: z-score for the desired confidence level (default 1.96 = 95 %).
    Returns:
        (low, high) both clipped to [0.0, 1.0], rounded to at most 10 dp.
    Raises:
        ValueError: When trials == 0.
    """
    if trials == 0:
        raise ValueError("trials must be > 0 to compute a Wilson interval")

    n = trials
    p_hat = successes / n
    z_sq = z * z

    denominator = 1.0 + z_sq / n
    center = (p_hat + z_sq / (2.0 * n)) / denominator
    margin = z * math.sqrt(p_hat * (1.0 - p_hat) / n + z_sq / (4.0 * n * n)) / denominator

    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return (low, high)


def pass_rate(successes: int, trials: int) -> float:
    """Return the raw pass rate as a float in [0.0, 1.0].

    Args:
        successes: Number of passing trials.
        trials: Total number of trials (must be > 0).
    Returns:
        successes / trials.
    Raises:
        ValueError: When trials == 0.
    """
    if trials == 0:
        raise ValueError("trials must be > 0 to compute a pass rate")
    return successes / trials
