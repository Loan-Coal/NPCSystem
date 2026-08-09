"""
Module: test_adjudicate
Layer: test (unit)
Purpose: Unit tests for adjudicate.py — the resumable adjudication CLI for EVAL-P5.3.
Dependencies: pathlib, pytest, calibration_records, adjudicate (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from calibration_records import CalibrationLabel, write_calibration_labels
from adjudicate import _format_row_prompt, apply_verdict, collect_pending


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LABELLER = "claude-opus-5"


def _make_label(
    index: int,
    *,
    scorer: str = "tone_judge",
    scorer_verdict: bool = True,
    pre_label: bool = True,
    human_verdict: bool | None = None,
    adjudicated_at: str | None = None,
    criteria: str = "",
    player_message: str = "",
    observed: dict[str, object] | None = None,
) -> CalibrationLabel:
    """Build a CalibrationLabel for testing."""
    return CalibrationLabel(
        record_id=f"case_{index:03d}:{scorer}:0",
        scorer=scorer,
        output_text=f"Output text for row {index}.",
        scorer_verdict=scorer_verdict,
        pre_label=pre_label,
        pre_labeller_model=_LABELLER,
        human_verdict=human_verdict,
        adjudicated_at=adjudicated_at,
        notes="",
        criteria=criteria,
        player_message=player_message,
        observed=observed or {},
    )


def _make_rows(
    count: int,
    adjudicated_indices: set[int] | None = None,
) -> list[CalibrationLabel]:
    """Build `count` rows; rows at `adjudicated_indices` have a human_verdict set."""
    adj = adjudicated_indices or set()
    return [
        _make_label(
            i,
            human_verdict=True if i in adj else None,
            adjudicated_at="2026-08-07T10:00:00+00:00" if i in adj else None,
        )
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# RED anchor — must fail until adjudicate.py exists
# ---------------------------------------------------------------------------


def test_resume_skips_already_adjudicated_rows(tmp_path: Path) -> None:
    """On a 5-row file with 2 adjudicated, collect_pending returns exactly 3 rows."""
    rows = _make_rows(5, adjudicated_indices={0, 3})
    pending = collect_pending(rows)
    assert len(pending) == 3
    for row in pending:
        assert row.human_verdict is None


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


def test_flip_sets_human_verdict_opposite_to_pre_label(tmp_path: Path) -> None:
    """Flipping a row writes human_verdict != pre_label, leaving pre_label untouched."""
    row = _make_label(0, pre_label=True)
    timestamp = "2026-08-07T12:00:00+00:00"
    updated = apply_verdict(row, "flip", timestamp)
    assert updated.pre_label is True
    assert updated.human_verdict is False
    assert updated.adjudicated_at == timestamp


def test_keep_sets_human_verdict_equal_to_pre_label(tmp_path: Path) -> None:
    """Keeping a row writes human_verdict == pre_label."""
    row = _make_label(0, pre_label=False)
    timestamp = "2026-08-07T12:00:00+00:00"
    updated = apply_verdict(row, "keep", timestamp)
    assert updated.pre_label is False
    assert updated.human_verdict is False
    assert updated.adjudicated_at == timestamp


def test_skip_leaves_row_unadjudicated() -> None:
    """Skipping a row leaves human_verdict=None and adjudicated_at=None."""
    row = _make_label(0, pre_label=True)
    timestamp = "2026-08-07T12:00:00+00:00"
    updated = apply_verdict(row, "skip", timestamp)
    assert updated.human_verdict is None
    assert updated.adjudicated_at is None


def test_apply_verdict_does_not_mutate_original() -> None:
    """apply_verdict returns a new CalibrationLabel; the original is unchanged."""
    row = _make_label(0, pre_label=True)
    apply_verdict(row, "flip", "2026-08-07T12:00:00+00:00")
    assert row.human_verdict is None


def test_collect_pending_all_unadjudicated() -> None:
    """collect_pending returns all rows when none are adjudicated."""
    rows = _make_rows(4)
    assert len(collect_pending(rows)) == 4


def test_collect_pending_all_adjudicated() -> None:
    """collect_pending returns an empty list when all rows are adjudicated."""
    rows = _make_rows(4, adjudicated_indices={0, 1, 2, 3})
    assert len(collect_pending(rows)) == 0


def test_flip_pre_label_false_produces_human_verdict_true() -> None:
    """Flipping a negative pre_label produces a positive human_verdict."""
    row = _make_label(0, pre_label=False)
    updated = apply_verdict(row, "flip", "2026-08-07T12:00:00+00:00")
    assert updated.human_verdict is True


def test_collect_pending_preserves_order() -> None:
    """collect_pending returns pending rows in their original file order."""
    rows = _make_rows(6, adjudicated_indices={1, 4})
    pending = collect_pending(rows)
    expected_indices = [0, 2, 3, 5]
    for i, row in enumerate(pending):
        assert row.record_id == f"case_{expected_indices[i]:03d}:tone_judge:0"


# ---------------------------------------------------------------------------
# Display: criteria / observed must be visible, or adjudication is a coin flip
# ---------------------------------------------------------------------------


def test_format_row_prompt_includes_criteria() -> None:
    """The adjudication prompt shows the scorer's criteria, not just pre_label."""
    row = _make_label(0, criteria="The response must contain at least one of: 'sorry', 'apologise'.")
    rendered = _format_row_prompt(row, 1, 1)
    assert "sorry" in rendered
    assert "apologise" in rendered


def test_format_row_prompt_includes_observed_when_present() -> None:
    """When observed is non-empty (in_set/range/schema scorers), its value is shown."""
    row = _make_label(
        0,
        scorer="in_set",
        criteria="The response field `facial_expression.type` must be one of: 'neutral', 'grim'.",
        observed={"facial_expression.type": "grim"},
    )
    rendered = _format_row_prompt(row, 1, 1)
    assert "facial_expression.type" in rendered
    assert "grim" in rendered


def test_format_row_prompt_includes_player_message_when_present() -> None:
    """The player's turn that prompted the response is shown for context."""
    row = _make_label(0, player_message="What did you see, guard?")
    rendered = _format_row_prompt(row, 1, 1)
    assert "What did you see, guard?" in rendered
