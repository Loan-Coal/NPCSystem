"""
Module: test_baseline_selection
Layer: test (unit)
Purpose: RED anchor + behaviour tests for evals/baseline_selection.py — choosing
         WHICH prior trend row a candidate run is gated against (EVAL-P23 Defect B).
         latest_row() returns the most recent row regardless of harness_version,
         so a case/prompt/matcher edit made the gate return a confident verdict on
         an incomparable pair while compare.py correctly refused the same pair.
Dependencies: pytest; baseline_selection, trend_store (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from baseline_selection import (
    BaselineChoice,
    format_baseline_choice,
    select_baseline,
    select_named_baseline,
)
from trend_store import RateWithCI, TrendRow


def _row(gen_id: str, harness_version: str = "v1", recorded_at: str = "2026-08-10T00:00:00+00:00") -> TrendRow:
    return TrendRow(
        gen_id=gen_id,
        harness_version=harness_version,
        recorded_at=recorded_at,
        guard=RateWithCI(rate=0.9, ci_low=0.85, ci_high=0.95, n=94),
    )


# ---------------------------------------------------------------------------
# RED anchors
# ---------------------------------------------------------------------------


def test_gate_refuses_when_no_comparable_baseline_exists() -> None:
    """A store full of rows recorded under a different harness_version is not a
    baseline. harness_version hashes evals/cases/, prompts/eval/ and matchers.py
    — editing a case or a judge criterion changes it, and compare.py refuses that
    pair. The gate must refuse it too rather than returning a confident verdict."""
    rows = [_row("gen_a", harness_version="v1"), _row("gen_b", harness_version="v1")]
    choice = select_baseline("v2", rows)
    assert choice.row is None
    assert choice.refusal  # names why, never a bare None
    assert "v2" in choice.refusal


def test_gate_walks_back_past_an_incomparable_row() -> None:
    """The most recent row is not automatically the baseline. When a run under a
    changed harness_version sits on top, the gate walks back to the most recent
    row that IS comparable rather than refusing outright."""
    rows = [
        _row("gen_old", harness_version="v1", recorded_at="2026-08-01T00:00:00+00:00"),
        _row("gen_comparable", harness_version="v1", recorded_at="2026-08-05T00:00:00+00:00"),
        _row("gen_other_harness", harness_version="v2", recorded_at="2026-08-09T00:00:00+00:00"),
    ]
    choice = select_baseline("v1", rows)
    assert choice.row is not None
    assert choice.row.gen_id == "gen_comparable"  # most recent comparable, not most recent
    assert choice.skipped == 1
    assert choice.rows_back == 2  # two rows back from the end of the store


def test_gate_output_names_the_chosen_baseline_and_its_age() -> None:
    """Comparing against a much older run must be visible, never silent — the
    output names the gen_id, how many rows back it sits, and how old it is."""
    rows = [
        _row("gen_ancient", harness_version="v1", recorded_at="2026-06-01T00:00:00+00:00"),
        _row("gen_other_harness", harness_version="v2", recorded_at="2026-08-09T00:00:00+00:00"),
    ]
    choice = select_baseline("v1", rows)
    text = format_baseline_choice(choice, "2026-08-18T00:00:00+00:00")
    assert "gen_ancient" in text
    assert "78" in text  # days older: 2026-06-01 -> 2026-08-18
    assert "back" in text  # how many rows back it sits
    assert "skipped 1" in text  # the walked-past incomparable row is accounted for


# ---------------------------------------------------------------------------
# Behaviour
# ---------------------------------------------------------------------------


def test_empty_store_refuses_with_its_own_reason() -> None:
    choice = select_baseline("v1", [])
    assert choice.row is None
    assert choice.refusal


def test_most_recent_comparable_row_wins_when_several_match() -> None:
    rows = [_row("gen_a"), _row("gen_b"), _row("gen_c")]
    choice = select_baseline("v1", rows)
    assert choice.row is not None
    assert choice.row.gen_id == "gen_c"
    assert choice.rows_back == 1
    assert choice.skipped == 0


def test_named_baseline_is_honoured_when_comparable() -> None:
    """An explicit -Baseline override must gate against exactly that row, so the
    compare step (7) and the gate (8) report on the same pair."""
    rows = [_row("gen_a"), _row("gen_b"), _row("gen_c")]
    choice = select_named_baseline("gen_a", "v1", rows)
    assert choice.row is not None
    assert choice.row.gen_id == "gen_a"


def test_named_baseline_that_is_absent_refuses() -> None:
    choice = select_named_baseline("gen_missing", "v1", [_row("gen_a")])
    assert choice.row is None
    assert "gen_missing" in choice.refusal


def test_named_baseline_from_another_harness_version_refuses() -> None:
    """An explicit override cannot buy its way past comparability — that is the
    whole defect this module exists to close."""
    choice = select_named_baseline("gen_a", "v2", [_row("gen_a", harness_version="v1")])
    assert choice.row is None
    assert "harness_version" in choice.refusal


def test_format_of_a_refusal_states_the_refusal() -> None:
    choice = BaselineChoice(refusal="nothing comparable")
    assert "nothing comparable" in format_baseline_choice(choice, "2026-08-18T00:00:00+00:00")


def test_unparseable_timestamps_do_not_crash_the_naming() -> None:
    """An age that cannot be computed must degrade to naming the row, never
    take down the gate that was about to report a verdict."""
    rows = [_row("gen_a", recorded_at="not-a-timestamp")]
    text = format_baseline_choice(select_baseline("v1", rows), "also-not-a-timestamp")
    assert "gen_a" in text
