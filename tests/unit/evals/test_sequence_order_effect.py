"""
Module: test_sequence_order_effect
Layer: test (unit)
Purpose: Tests for evals/sequence_order_effect.py — Cochran's Q and first-vs-last
         McNemar pooled across the promoted scenario battery (SEQUENCE_STATS_POLICY §4).
Dependencies: pytest, sequence_order_effect (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from sequence_order_effect import order_effect_check

_T, _F = True, False


def test_no_order_effect_when_outcomes_constant_across_repetitions() -> None:
    """Every scenario's own rate is flat across reps -> Cochran's Q is not computable
    when every row is uniform, but the rates_by_repetition are still reported."""
    outcomes = [
        [_T, _T, _T],
        [_F, _F, _F],
        [_T, _T, _T],
    ]
    result = order_effect_check(outcomes)
    assert result.computable is False
    assert result.reason is not None
    assert result.rates_by_repetition == (2 / 3, 2 / 3, 2 / 3)


def test_order_effect_detected_when_later_reps_fail_more() -> None:
    """A systematic decline in pass rate across repetition index is detectable."""
    outcomes = [
        [_T, _T, _F],
        [_T, _F, _F],
        [_T, _T, _F],
        [_T, _F, _F],
        [_T, _T, _F],
        [_T, _F, _F],
    ]
    result = order_effect_check(outcomes)
    assert result.computable is True
    assert result.cochrans_q is not None
    assert result.cochrans_q_p is not None
    assert result.rates_by_repetition[0] == 1.0
    assert result.rates_by_repetition[-1] == 0.0


def test_mcnemar_p_none_when_no_discordant_pairs_at_ends() -> None:
    """rep[0] and rep[-1] agree on every scenario -> McNemar undefined -> None."""
    outcomes = [
        [_T, _F, _T],
        [_F, _T, _F],
    ]
    result = order_effect_check(outcomes)
    assert result.mcnemar_p is None


def test_mcnemar_p_computed_when_ends_disagree() -> None:
    """rep[0] vs rep[-1] disagree on at least one scenario -> a p-value is produced."""
    outcomes = [
        [_T, _T, _F],  # passed first, failed last
        [_F, _T, _T],  # failed first, passed last
        [_T, _T, _T],
    ]
    result = order_effect_check(outcomes)
    assert result.mcnemar_p is not None
    assert 0.0 < result.mcnemar_p <= 1.0


def test_k_below_three_skips_cochrans_q() -> None:
    """Per SEQUENCE_STATS_POLICY §4.2, k=2 skips the omnibus test entirely."""
    outcomes = [
        [_T, _F],
        [_F, _T],
    ]
    result = order_effect_check(outcomes)
    assert result.computable is False
    assert "k=2" in (result.reason or "")
    assert result.cochrans_q is None
    assert result.cochrans_q_p is None


def test_rates_by_repetition_length_matches_k() -> None:
    """One pooled pass rate per repetition index."""
    outcomes = [[_T, _F, _T, _T], [_F, _F, _T, _F]]
    result = order_effect_check(outcomes)
    assert len(result.rates_by_repetition) == 4


def test_empty_outcomes_raises() -> None:
    """At least one scenario row is required."""
    with pytest.raises(ValueError):
        order_effect_check([])


def test_inconsistent_row_lengths_raise() -> None:
    """Every scenario must share the same k (same run)."""
    with pytest.raises(ValueError):
        order_effect_check([[_T, _F, _T], [_T, _F]])
