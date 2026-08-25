"""
Module: test_rate_stats
Layer: test (unit)
Purpose: Table-driven tests for evals/rate_stats.py — wilson_interval and pass_rate.
         Hand-worked arithmetic is documented inline so every digit is traceable.
Dependencies: math, pytest, rate_stats (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import math

import pytest

from rate_stats import pass_rate, wilson_interval

# ---------------------------------------------------------------------------
# Hand-worked Wilson score arithmetic (z=1.96, z²=3.8416)
#
# Formula:
#   p̂ = successes / trials
#   center = (p̂ + z²/(2n)) / (1 + z²/n)
#   margin = z * sqrt(p̂(1-p̂)/n + z²/(4n²)) / (1 + z²/n)
#   low = max(0, center - margin)
#   high = min(1, center + margin)
#
# (0, 3): p̂=0.0, z²/n=1.2805, z²/(2n)=0.6403
#   center = 0.6403 / 2.2805 = 0.2807
#   margin = 1.96 * sqrt(0 + 0.1067) / 2.2805 = 1.96*0.3267/2.2805 = 0.2807
#   → [0.000, 0.562]
#
# (3, 3): p̂=1.0, z²/n=1.2805, z²/(2n)=0.6403
#   center = 1.6403 / 2.2805 = 0.7192
#   margin = 1.96 * sqrt(0 + 0.1067) / 2.2805 = 0.2807
#   → [0.438, 1.000]  (high clipped to 1.0)
#
# (3, 5): p̂=0.6, z²/n=0.7683, z²/(2n)=0.3842
#   center = 0.9842 / 1.7683 = 0.5565
#   margin = 1.96 * sqrt(0.048 + 0.03842) / 1.7683 = 1.96*0.2940/1.7683 = 0.3257
#   → [0.231, 0.882]
# ---------------------------------------------------------------------------

_WILSON_TABLE = [
    # (successes, trials, expected_low, expected_high)
    (0, 3, 0.000, 0.562),
    (3, 3, 0.438, 1.000),
    (3, 5, 0.231, 0.882),
]


def test_wilson_3_of_3() -> None:
    """Wilson interval for 3/3 gives [0.438, 1.000] to 3 dp."""
    low, high = wilson_interval(3, 3)
    assert round(low, 3) == 0.438
    assert round(high, 3) == 1.000


@pytest.mark.parametrize("successes,trials,exp_low,exp_high", _WILSON_TABLE)
def test_wilson_table_driven(
    successes: int, trials: int, exp_low: float, exp_high: float
) -> None:
    """Table-driven check: every row matches to 3 dp."""
    low, high = wilson_interval(successes, trials)
    assert round(low, 3) == exp_low, f"low mismatch for {successes}/{trials}"
    assert round(high, 3) == exp_high, f"high mismatch for {successes}/{trials}"


def test_wilson_zero_trials_raises() -> None:
    """wilson_interval with trials=0 must raise, not return [0.0, 1.0]."""
    with pytest.raises(ValueError, match="trials"):
        wilson_interval(0, 0)


def test_wilson_returns_tuple_of_floats() -> None:
    """Return type is a 2-tuple of floats, both in [0, 1]."""
    result = wilson_interval(2, 4)
    assert isinstance(result, tuple)
    assert len(result) == 2
    low, high = result
    assert 0.0 <= low <= high <= 1.0


def test_wilson_bounds_clipped() -> None:
    """Bounds must be clipped to [0, 1] — never negative or above 1."""
    low, high = wilson_interval(0, 3)
    assert low >= 0.0
    low2, high2 = wilson_interval(3, 3)
    assert high2 <= 1.0


def test_pass_rate_basic() -> None:
    """pass_rate returns successes/trials as a float."""
    assert math.isclose(pass_rate(3, 5), 0.6)


def test_pass_rate_zero_trials_raises() -> None:
    """pass_rate with trials=0 must raise."""
    with pytest.raises(ValueError, match="trials"):
        pass_rate(0, 0)


def test_pass_rate_all_pass() -> None:
    """pass_rate(n, n) == 1.0."""
    assert math.isclose(pass_rate(5, 5), 1.0)


def test_pass_rate_none_pass() -> None:
    """pass_rate(0, n) == 0.0."""
    assert math.isclose(pass_rate(0, 5), 0.0)


# ---------------------------------------------------------------------------
# Degenerate intervals must be EXACT, not floating-point-approximate
# ---------------------------------------------------------------------------


def test_a_perfect_rate_has_an_upper_bound_of_exactly_one() -> None:
    """At successes == trials the Wilson upper bound is exactly 1.0 in closed form:
    centre and margin both reduce to (1 + z^2/2n) / (1 + z^2/n) + z^2/2n / (1 + z^2/n).
    The arithmetic as written returns 0.9999999999999999 for 42 of the first 140 n,
    and `min(1.0, ...)` cannot repair a value that is already below 1.0.

    This is not cosmetic. regression_gate compares `candidate.ci_high < baseline.rate`,
    so a battery scoring 100% on both sides of a comparison reads as a regression
    against ITSELF at those n — the exact failure DEC-185 exists to prevent, returning
    through float error rather than through the wrong comparison."""
    off_by_an_ulp = [n for n in range(1, 501) if wilson_interval(n, n)[1] != 1.0]
    assert off_by_an_ulp == [], (
        f"{len(off_by_an_ulp)} of 500 denominators return ci_high != 1.0 for a perfect "
        f"rate; first few: {off_by_an_ulp[:10]}"
    )


def test_a_zero_rate_has_a_lower_bound_of_exactly_zero() -> None:
    """The mirror case: at successes == 0 the Wilson lower bound is exactly 0.0.
    A gate reading `baseline.ci_low` would inherit the same class of error."""
    off_by_an_ulp = [n for n in range(1, 501) if wilson_interval(0, n)[0] != 0.0]
    assert off_by_an_ulp == []


def test_clamping_the_degenerate_ends_leaves_every_other_interval_untouched() -> None:
    """The clamp must apply ONLY at k==0 and k==n. Every interior interval keeps the
    arithmetic it had, so no published number moves."""
    for n in (7, 16, 78, 104):
        for k in range(1, n):
            low, high = wilson_interval(k, n)
            assert 0.0 < low < high < 1.0
