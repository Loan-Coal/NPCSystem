"""
Module: test_pre_label_replacement
Layer: test (unit)
Purpose: RED anchor for ISSUE-175 — merge_labels silently discarded an incoming
         pre_label/pre_labeller_model for any matched row, whether or not
         criteria drifted, because pre_label is deliberately excluded from
         _MACHINE_FIELDS. That is correct for the default label-import path
         (incoming pre_label there is not necessarily fresh), but it made it
         impossible to import a genuine second-rater pass (Opus, EVAL-P22.3)
         over the 393 rows that already carry a pre_label from the first
         rater — every one of the new opinions was silently dropped. The
         --replace-pre-label opt-in (label_import.py CLI, merge_labels'
         replace_pre_label kwarg) fixes this without changing default
         behaviour.
Dependencies: pytest, label_merge, calibration_records (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from calibration_records import CalibrationLabel
from label_merge import merge_labels


def _label(record_id: str, **overrides: object) -> CalibrationLabel:
    base: dict[str, object] = dict(
        record_id=record_id,
        scorer="tone_judge",
        output_text="some output",
        scorer_verdict=True,
        pre_label=True,
        pre_labeller_model="human-lohann",
        human_verdict=True,
        adjudicated_at="2026-08-01T00:00:00+00:00",
        notes="",
        criteria="be gruff",
        player_message="where are the troops",
        observed={},
        output_sha256="abc123",
        criteria_sha256="def456",
    )
    base.update(overrides)
    return CalibrationLabel(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_replace_pre_label_overwrites_existing_second_rater_opinion() -> None:
    """A genuine second-rater import (--replace-pre-label) must actually land.

    Without the fix: incoming's pre_label/pre_labeller_model are never in
    _MACHINE_FIELDS, so a fresh Opus pre-labelling pass over the existing
    393 rows silently disappears on --merge, and the secondary calibration
    axis stays exactly as tautological as before the import ran.
    """
    existing = _label("case_x:tone_judge:0#r0", pre_label=True, pre_labeller_model="human-lohann")
    incoming = _label("case_x:tone_judge:0#r0", pre_label=False, pre_labeller_model="claude-opus-5")
    result = merge_labels([existing], [incoming], replace_pre_label=True)
    merged = result.rows[0]
    assert merged.pre_label is False
    assert merged.pre_labeller_model == "claude-opus-5"


def test_replace_pre_label_never_touches_human_verdict() -> None:
    """The opt-in only ever changes pre_label/pre_labeller_model, never the
    adjudicated human_verdict — that guarantee is load-bearing and must not
    regress alongside this fix."""
    existing = _label("case_x:tone_judge:0#r0", human_verdict=True, notes="original note")
    incoming = _label(
        "case_x:tone_judge:0#r0", pre_label=False, pre_labeller_model="claude-opus-5",
        human_verdict=False, notes="incoming note",
    )
    result = merge_labels([existing], [incoming], replace_pre_label=True)
    merged = result.rows[0]
    assert merged.human_verdict is True  # existing's verdict, untouched
    assert merged.notes == "original note"  # existing's notes, untouched
    assert merged.pre_label is False  # incoming's replaced value


# ---------------------------------------------------------------------------
# Behaviour: default (opt-out) path is unchanged
# ---------------------------------------------------------------------------


def test_default_merge_still_preserves_existing_pre_label() -> None:
    """Without the flag, behaviour is exactly what it always was — a bare
    --merge run does not accidentally start overwriting pre_label."""
    existing = _label("case_x:tone_judge:0#r0", pre_label=True, pre_labeller_model="human-lohann")
    incoming = _label("case_x:tone_judge:0#r0", pre_label=False, pre_labeller_model="claude-opus-5")
    result = merge_labels([existing], [incoming])
    merged = result.rows[0]
    assert merged.pre_label is True
    assert merged.pre_labeller_model == "human-lohann"


def test_replace_pre_label_under_drift_keeps_incoming_not_cleared() -> None:
    """When criteria drifted AND replace_pre_label is set, the incoming
    pre_label reflects an opinion on the NEW criteria and is trustworthy —
    it must not be cleared to None the way the default drift path does."""
    existing = _label(
        "case_x:tone_judge:0#r0", criteria_sha256="old-hash",
        pre_label=True, pre_labeller_model="human-lohann", human_verdict=True,
    )
    incoming = _label(
        "case_x:tone_judge:0#r0", criteria_sha256="new-hash",
        pre_label=False, pre_labeller_model="claude-opus-5",
    )
    result = merge_labels([existing], [incoming], replace_pre_label=True)
    merged = result.rows[0]
    assert merged.needs_review is True  # drift still flags for human re-review
    assert merged.pre_label is False  # but the fresh opinion is kept, not cleared
    assert merged.pre_labeller_model == "claude-opus-5"
