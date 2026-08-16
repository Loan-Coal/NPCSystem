"""
Module: test_pre_label_drift
Layer: test (unit)
Purpose: RED anchor for EVAL-P20.3a Step 4 (ISSUE-153) — a drifted row must have
         its pre_label cleared to None (not silently carried forward stale), and
         the three secondary-axis calibration functions (pre_label_confusion_counts,
         pre_label_kappa, pre_label_kappa_interval) must exclude pre_label is None
         rows rather than silently miscounting them.
Dependencies: pytest, label_merge, calibration, calibration_records (evals/)
Used by: pytest (make test / make check)
"""
from __future__ import annotations

import pytest

from calibration import pre_label_confusion_counts, pre_label_kappa, pre_label_kappa_interval
from calibration_records import CalibrationLabel
from label_merge import merge_labels


def _label(record_id: str, **overrides: object) -> CalibrationLabel:
    base: dict[str, object] = dict(
        record_id=record_id,
        scorer="tone_judge",
        output_text="some output",
        scorer_verdict=True,
        pre_label=True,
        pre_labeller_model="claude-opus-5",
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


def test_drifted_pre_label_excluded_from_secondary_kappa() -> None:
    """A drifted row's pre_label is cleared to None and excluded from the secondary axis.

    Without the fix: CalibrationLabel.pre_label is a plain bool, _MACHINE_FIELDS
    never refreshes it, and a re-adjudicated row keeps whatever pre_label it had
    from its first import forever — a stale reference-labeller opinion silently
    re-enters pre_label_confusion_counts/pre_label_kappa/pre_label_kappa_interval.

    Drift trigger uses criteria_sha256, not output_sha256 — EVAL-P20.3b
    (DEC-181) redefined drift as criteria-only; an output_sha256 change alone
    is no longer drift (see test_verdict_only_drift.py).
    """
    existing = _label("case_x:tone_judge:0#r0", criteria_sha256="def456", human_verdict=True)
    incoming = _label("case_x:tone_judge:0#r0", criteria_sha256="changed-criteria-hash")
    result = merge_labels([existing], [incoming])
    merged = result.rows[0]
    assert merged.needs_review is True
    assert merged.pre_label is None
    assert merged.pre_labeller_model == ""


# ---------------------------------------------------------------------------
# Behaviour tests
# ---------------------------------------------------------------------------


def test_undrifted_pre_label_is_preserved() -> None:
    """A row with no drift keeps its existing pre_label untouched."""
    existing = _label("case_y:tone_judge:0#r0", pre_label=False, human_verdict=True)
    incoming = _label("case_y:tone_judge:0#r0", pre_label=True)  # incoming pre_label ignored
    result = merge_labels([existing], [incoming])
    merged = result.rows[0]
    assert merged.needs_review is False
    assert merged.pre_label is False  # existing value preserved, not incoming's


def test_pre_label_confusion_counts_excludes_none_rows() -> None:
    """Rows with pre_label=None don't silently vanish from the tally — they're excluded."""
    rows = [
        _label("case_a:tone_judge:0#r0", pre_label=True, human_verdict=True),
        _label("case_b:tone_judge:0#r0", pre_label=None, human_verdict=True),
        _label("case_c:tone_judge:0#r0", pre_label=False, human_verdict=False),
    ]
    counts = pre_label_confusion_counts(rows)
    assert counts.n == 2  # only the two rows with a real pre_label
    assert counts.n_excluded_pre_label_cleared == 1


def test_pre_label_kappa_requires_two_rows_with_pre_label() -> None:
    """Two adjudicated rows exist, but only one has a real pre_label — must raise."""
    rows = [
        _label("case_a:tone_judge:0#r0", pre_label=True, human_verdict=True),
        _label("case_b:tone_judge:0#r0", pre_label=None, human_verdict=False),
    ]
    with pytest.raises(ValueError, match="pre_label"):
        pre_label_kappa(rows)


def test_pre_label_kappa_interval_excludes_none_pre_label_rows() -> None:
    """kappa_interval's cluster set must not include pre_label=None rows."""
    rows = [
        _label(f"case_{i}:tone_judge:0#r0", pre_label=(i % 2 == 0), human_verdict=(i % 2 == 0))
        for i in range(6)
    ] + [
        _label("case_stale:tone_judge:0#r0", pre_label=None, human_verdict=True),
    ]
    ci = pre_label_kappa_interval(rows, resamples=50, seed=1)
    assert ci.n_rows == 6  # the pre_label=None row excluded from the cluster set
