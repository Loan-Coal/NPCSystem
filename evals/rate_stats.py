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


def _exact_at_degenerate_ends(
    low: float, high: float, successes: int, trials: int
) -> tuple[float, float]:
    """Return the interval with its all-pass / all-fail ends made exact.

    At p̂=1 the Wilson upper bound is exactly 1 in closed form —
    (1 + z²/2n + z²/2n) / (1 + z²/n) — and at p̂=0 the lower bound is exactly 0.
    Evaluated in floating point the upper bound comes back as
    0.9999999999999999 for 42 of the first 140 denominators, and
    `min(1.0, ...)` cannot repair a value already below 1.0.

    That hairline matters because regression_gate compares
    `candidate.ci_high < baseline.rate`: without this, a battery scoring 100%
    on both sides of a comparison reads as a regression against ITSELF —
    DEC-185's failure mode returning through float error rather than through
    the wrong comparison, and invisible to the single-denominator
    self-comparison test DEC-185 left behind. Found 2026-08-25 while sizing
    EVAL-P22B.2, the no-op false-positive check (DEC-196).

    Args:
        low: Computed lower bound.
        high: Computed upper bound.
        successes: Passing trials.
        trials: Total trials.
    Returns:
        (low, high) with the degenerate end replaced by its exact value; every
        interior interval is returned untouched.
    """
    if successes == trials:
        high = 1.0
    if successes == 0:
        low = 0.0
    return (low, high)


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
        (low, high) both clipped to [0.0, 1.0]. The degenerate ends are exact:
        successes == trials yields high == 1.0 and successes == 0 yields
        low == 0.0, rather than the floating-point value a hair away from it.
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

    return _exact_at_degenerate_ends(
        max(0.0, center - margin), min(1.0, center + margin), successes, trials
    )


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
