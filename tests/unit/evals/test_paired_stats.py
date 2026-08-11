"""
Module: test_paired_stats
Layer: test (unit)
Purpose: Tests for evals/paired_stats.py — mcnemar_exact and paired_compare.
Dependencies: pytest, paired_stats (evals/), case_stats (evals/), rate_stats (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from case_stats import CaseStat
from compare import _JudgedRow, _build_case_stats
from paired_stats import PairedResult, boundary_ci_note, is_boundary_ci, mcnemar_exact, paired_compare


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stat(case_id: str, passes: int, k: int) -> CaseStat:
    """Build a minimal CaseStat for paired_compare fixture construction."""
    from case_stats import classify
    from rate_stats import pass_rate, wilson_interval

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


# ---------------------------------------------------------------------------
# EVAL-P16.4: McNemar on cases, not expectation slots
# ---------------------------------------------------------------------------


def test_mcnemar_pairs_cases_not_expectation_slots():
    """Two cases with 3 expectation slots each; both regress.

    Scenario: case_a and case_b each have 3 slots (tone:0, tone:1, refusal:0).
    Before: all slots pass. After: all slots fail.

    At slot level: b=6 regressed, c=0 improved → mcnemar_exact(6,0) = 0.031 "worse".
    At case level: b=2 regressed, c=0 improved → mcnemar_exact(2,0) = 0.5 no_detectable_change.

    The correct (case-level) result is p=0.5 / no_detectable_change.
    """
    before_rows = [
        _JudgedRow(record_id="case_a:tone_judge:0", case_id="case_a", passed=True),
        _JudgedRow(record_id="case_a:tone_judge:1", case_id="case_a", passed=True),
        _JudgedRow(record_id="case_a:refusal_judge:0", case_id="case_a", passed=True),
        _JudgedRow(record_id="case_b:tone_judge:0", case_id="case_b", passed=True),
        _JudgedRow(record_id="case_b:tone_judge:1", case_id="case_b", passed=True),
        _JudgedRow(record_id="case_b:refusal_judge:0", case_id="case_b", passed=True),
    ]
    after_rows = [
        _JudgedRow(record_id="case_a:tone_judge:0", case_id="case_a", passed=False),
        _JudgedRow(record_id="case_a:tone_judge:1", case_id="case_a", passed=False),
        _JudgedRow(record_id="case_a:refusal_judge:0", case_id="case_a", passed=False),
        _JudgedRow(record_id="case_b:tone_judge:0", case_id="case_b", passed=False),
        _JudgedRow(record_id="case_b:tone_judge:1", case_id="case_b", passed=False),
        _JudgedRow(record_id="case_b:refusal_judge:0", case_id="case_b", passed=False),
    ]

    before_stats = _build_case_stats(before_rows)
    after_stats = _build_case_stats(after_rows)

    # Case-level: b=2 (case_a and case_b both regress), c=0
    result = paired_compare(before_stats, after_stats)
    assert result.regressed == 2
    assert result.improved == 0
    assert result.p_value == pytest.approx(0.5)
    assert result.verdict == "no_detectable_change"


# ---------------------------------------------------------------------------
# EVAL-P16.4: Boundary-aware CI utilities
# ---------------------------------------------------------------------------


def test_is_boundary_ci_detects_degenerate_interval():
    """A CI where lo == hi is at the boundary (zero uncertainty)."""
    assert is_boundary_ci(1.0, 1.0) is True
    assert is_boundary_ci(0.0, 0.0) is True
    assert is_boundary_ci(0.663, 0.663) is True


def test_is_boundary_ci_passes_valid_interval():
    """A CI with lo < hi is not at the boundary."""
    assert is_boundary_ci(0.0, 1.0) is False
    assert is_boundary_ci(0.663, 1.000) is False
    assert is_boundary_ci(0.999, 1.000) is False


def test_boundary_ci_note_names_cluster_count():
    """boundary_ci_note includes n_clusters in the formatted message."""
    note = boundary_ci_note(3)
    assert "boundary" in note
    assert "3" in note
