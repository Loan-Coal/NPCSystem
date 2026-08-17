"""
Module: test_label_sampling
Layer: test (unit)
Purpose: RED anchor + behaviour tests for evals/label_sampling.py — deterministic
         stratified ordering for a full-corpus labelling pass (EVAL-P22.1,
         rescoped from a cost-driven ~150-row SAMPLE to a full-corpus ordering
         utility once labelling stopped meaning hours of human time).
Dependencies: pytest; label_sampling (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from label_sampling import coverage_report, order_for_labelling, stratify


def _rows(*specs: tuple[str, str, bool]) -> list[tuple[str, str, bool]]:
    return list(specs)


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_sample_is_stratified_by_verdict_not_just_kind() -> None:
    """A scorer dominated by passes must not silently swamp the front of the
    queue — its few failing rows are the rarest, highest-signal stratum and
    must surface early, not be diluted by drawing 'by scorer' alone (the
    exact failure this task exists to prevent: a sample of 525 passes and
    3 failures measures nothing about the failure class).
    """
    # keyword_none: 207 passes, 0 fails (the real measured shape).
    # keyword_any: 21 passes, 3 fails (the real measured shape).
    rows = (
        _rows(*[(f"kn_{i}", "keyword_none", True) for i in range(207)])
        + _rows(*[(f"ka_{i}", "keyword_any", True) for i in range(21)])
        + _rows(*[(f"kaf_{i}", "keyword_any", False) for i in range(3)])
    )
    ordered = order_for_labelling(rows, seed=1)
    first_ten = set(ordered[:10])
    # the 3-row failing stratum (rarest of all) must appear inside the first
    # ten items, not somewhere past the 207-row passing stratum.
    assert {"kaf_0", "kaf_1", "kaf_2"} <= first_ten


# ---------------------------------------------------------------------------
# stratify()
# ---------------------------------------------------------------------------


def test_stratify_groups_by_scorer_and_verdict() -> None:
    rows = _rows(("a", "tone_judge", True), ("b", "tone_judge", True), ("c", "tone_judge", False))
    strata = stratify(rows)
    assert len(strata) == 2
    by_verdict = {s.verdict: s for s in strata}
    assert set(by_verdict[True].keys) == {"a", "b"}
    assert by_verdict[False].keys == ("c",)


def test_stratify_orders_smallest_stratum_first() -> None:
    rows = (
        _rows(*[(f"p{i}", "x", True) for i in range(10)])
        + _rows(("f0", "x", False))
    )
    strata = stratify(rows)
    assert strata[0].verdict is False
    assert len(strata[0].keys) == 1


# ---------------------------------------------------------------------------
# order_for_labelling() — reproducibility
# ---------------------------------------------------------------------------


def test_order_for_labelling_is_reproducible_under_a_recorded_seed() -> None:
    rows = _rows(*[(f"k{i}", "tone_judge", i % 2 == 0) for i in range(20)])
    first = order_for_labelling(rows, seed=42)
    second = order_for_labelling(rows, seed=42)
    assert first == second


def test_order_for_labelling_differs_across_seeds() -> None:
    rows = _rows(*[(f"k{i}", "tone_judge", i % 2 == 0) for i in range(20)])
    a = order_for_labelling(rows, seed=1)
    b = order_for_labelling(rows, seed=2)
    assert a != b


def test_order_for_labelling_preserves_every_row() -> None:
    rows = _rows(
        ("a", "tone_judge", True), ("b", "tone_judge", False), ("c", "affirms_judge", True),
    )
    ordered = order_for_labelling(rows, seed=0)
    assert sorted(ordered) == sorted(["a", "b", "c"])


# ---------------------------------------------------------------------------
# coverage_report() — naming what a labelling pass cannot measure
# ---------------------------------------------------------------------------


def test_coverage_report_names_a_scorer_with_zero_failures() -> None:
    """The measured real-corpus finding this exists to catch: keyword_none
    has 207 rows and not one failure — its failure-class accuracy is
    unmeasurable from this corpus no matter how thoroughly it's labelled."""
    rows = _rows(*[(f"kn_{i}", "keyword_none", True) for i in range(207)])
    gaps = coverage_report(rows)
    assert "keyword_none: zero rows with verdict=False" in gaps


def test_coverage_report_empty_when_both_verdicts_present() -> None:
    rows = _rows(("a", "tone_judge", True), ("b", "tone_judge", False))
    assert coverage_report(rows) == []
