"""
Module: test_paired_stats
Layer: test (unit)
Purpose: Tests for evals/paired_stats.py — mcnemar_exact and paired_compare.
Dependencies: pytest, paired_stats (evals/), case_stats (evals/), statistics (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from case_stats import CaseStat
from paired_stats import PairedResult, mcnemar_exact, paired_compare


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stat(case_id: str, passes: int, k: int) -> CaseStat:
    """Build a minimal CaseStat for paired_compare fixture construction."""
    from case_stats import classify
    from statistics import pass_rate, wilson_interval

    rate = pass_rate(passes, k)
    ci_low, ci_high = wilson_interval(passes, k)
    return CaseStat(
        case_id=case_id,
        k=k,
        passes=passes,
        pass_rate=rate,
        ci_low=ci_low,
        ci_high=ci_high,
        classification=classify(passes, k),
    )


# ---------------------------------------------------------------------------
# mcnemar_exact — worked-example table
# ---------------------------------------------------------------------------


def test_mcnemar_exact_matches_worked_example():
    """Pinned values against a hand-worked binomial table (two-sided, 3 dp).

    For discordant counts (b, c), the exact two-sided McNemar p-value is:
        p = min(1.0, 2 * sum_{k=0}^{min(b,c)} C(b+c, k) * 0.5^(b+c))

    | b | c | n | sum C(n,k) k=0..min(b,c)   | 2*sum / 2^n    | p (3 dp) |
    |---|---|---|----------------------------|----------------|----------|
    | 1 | 8 | 9 | C(9,0)+C(9,1) = 10         | 20/512 = 0.039 | 0.039    |
    | 2 | 7 | 9 | 10+C(9,2) = 46             | 92/512 = 0.180 | 0.180    |
    | 2 | 5 | 7 | C(7,0)+C(7,1)+C(7,2) = 29  | 58/128 = 0.453 | 0.453    |
    """
    assert round(mcnemar_exact(1, 8), 3) == 0.039
    assert round(mcnemar_exact(2, 7), 3) == 0.180
    assert round(mcnemar_exact(2, 5), 3) == 0.453


def test_mcnemar_exact_raises_when_no_discordant_pairs():
    """(b=0, c=0) must raise ValueError — test undefined with zero discordant pairs."""
    with pytest.raises(ValueError, match="discordant"):
        mcnemar_exact(0, 0)


def test_mcnemar_exact_caps_at_one():
    """When 2*sum > 2^n the result is capped at 1.0.

    (b=3, c=3): 2*(C(6,0)+...+C(6,3))/64 = 84/64 = 1.3125 → capped to 1.0.
    """
    assert mcnemar_exact(3, 3) == 1.0


# ---------------------------------------------------------------------------
# paired_compare — verdict fixtures
# ---------------------------------------------------------------------------


def test_paired_compare_better():
    """8 cases improve (fail→pass) and 1 regresses (pass→fail) reports 'better'.

    McNemar: b=1, c=8 → p≈0.039 < 0.05 and improved > regressed → 'better'.
    """
    before = tuple(
        _make_stat(f"case_{i:03d}", passes=0, k=1) for i in range(8)
    ) + (_make_stat("case_008", passes=1, k=1),)
    after = tuple(
        _make_stat(f"case_{i:03d}", passes=1, k=1) for i in range(8)
    ) + (_make_stat("case_008", passes=0, k=1),)
    result = paired_compare(before, after)
    assert result.improved == 8
    assert result.regressed == 1
    assert result.verdict == "better"


def test_paired_compare_no_detectable_change_symmetric():
    """3 improve and 3 regress → 'no_detectable_change', even though raw pass count rose.

    The 3 improving cases have k=3 (0→3 passes, +9 raw passes) while the 3
    regressing cases have k=1 (1→0 passes, -3 raw passes): raw total rises by 6.
    Despite this, McNemar on b=3, c=3 gives p=1.0 → no_detectable_change.

    Binary majority rule: passes*2 > k.
      improve_X before: passes=0, k=3 → 0*2=0 ≤ 3 → fail
      improve_X after:  passes=3, k=3 → 3*2=6 > 3 → pass
      regress_X before: passes=1, k=1 → 1*2=2 > 1 → pass
      regress_X after:  passes=0, k=1 → 0*2=0 ≤ 1 → fail
    """
    before_improve = tuple(
        _make_stat(f"improve_{i}", passes=0, k=3) for i in range(3)
    )
    after_improve = tuple(
        _make_stat(f"improve_{i}", passes=3, k=3) for i in range(3)
    )
    before_regress = tuple(
        _make_stat(f"regress_{i}", passes=1, k=1) for i in range(3)
    )
    after_regress = tuple(
        _make_stat(f"regress_{i}", passes=0, k=1) for i in range(3)
    )
    before = before_improve + before_regress
    after = after_improve + after_regress
    result = paired_compare(before, after)
    assert result.improved == 3
    assert result.regressed == 3
    assert result.verdict == "no_detectable_change"
