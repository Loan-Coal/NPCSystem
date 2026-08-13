"""
Module: chi_square
Layer: evals (utility)
Purpose: Hand-implemented chi-square upper-tail (survival) probability via the
         regularized incomplete gamma function. Uses only `math` — no scipy
         dependency, matching rate_stats.py's convention (DEC-162).
Dependencies: math
Used by: evals/sequence_order_effect.py (Cochran's Q p-value, EVAL-P12.4)
"""

from __future__ import annotations

import math

_MAX_ITERATIONS: int = 200
_CONVERGENCE_EPS: float = 1e-14
_CF_TINY: float = 1e-300


def _log_gamma_kernel(a: float, x: float) -> float:
    """Return the shared log-space prefactor exp(-x + a*ln(x) - ln(gamma(a)))."""
    return math.exp(-x + a * math.log(x) - math.lgamma(a))


def _lower_incomplete_gamma_series(a: float, x: float) -> float:
    """Series expansion for the regularized lower incomplete gamma P(a, x).

    Converges quickly for x < a + 1 (Numerical Recipes §6.2).

    Args:
        a: Shape parameter (a > 0).
        x: Upper limit of integration (0 <= x < a + 1).
    Returns:
        P(a, x) in [0.0, 1.0].
    """
    if x <= 0.0:
        return 0.0
    ap = a
    total = 1.0 / a
    delta = total
    for _ in range(_MAX_ITERATIONS):
        ap += 1.0
        delta *= x / ap
        total += delta
        if abs(delta) < abs(total) * _CONVERGENCE_EPS:
            break
    return total * _log_gamma_kernel(a, x)


def _upper_incomplete_gamma_continued_fraction(a: float, x: float) -> float:
    """Continued-fraction expansion for the regularized upper incomplete gamma Q(a, x).

    Converges quickly for x >= a + 1 (Numerical Recipes §6.2, Lentz's algorithm).

    Args:
        a: Shape parameter (a > 0).
        x: Lower limit of integration (x >= a + 1).
    Returns:
        Q(a, x) in [0.0, 1.0].
    """
    b = x + 1.0 - a
    c = 1.0 / _CF_TINY
    d = 1.0 / b
    h = d
    for i in range(1, _MAX_ITERATIONS):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < _CF_TINY:
            d = _CF_TINY
        c = b + an / c
        if abs(c) < _CF_TINY:
            c = _CF_TINY
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _CONVERGENCE_EPS:
            break
    return _log_gamma_kernel(a, x) * h


def chi2_sf(x: float, df: int) -> float:
    """Upper-tail probability that a chi-square(df) random variable exceeds x.

    Equivalent to the regularized upper incomplete gamma Q(df/2, x/2).

    Args:
        x: Observed chi-square statistic (x >= 0).
        df: Degrees of freedom (must be > 0).
    Returns:
        P(X > x) for X ~ chi-square(df), in [0.0, 1.0].
    Raises:
        ValueError: When df <= 0.
    """
    if df <= 0:
        raise ValueError(f"df must be > 0, got {df}")
    if x <= 0.0:
        return 1.0
    a = df / 2.0
    xx = x / 2.0
    if xx < a + 1.0:
        return max(0.0, min(1.0, 1.0 - _lower_incomplete_gamma_series(a, xx)))
    return max(0.0, min(1.0, _upper_incomplete_gamma_continued_fraction(a, xx)))
