"""
Module: test_drift_is_load_bearing
Layer: test (unit)
Purpose: Pins EVAL-P19.0 — `needs_review` (written by label_merge on content
         drift) must actually change behaviour: excluded from every
         calibration statistic, re-surfaced by adjudicate.collect_pending
         with its prior verdict attached, and reported as a WARNING by
         format_merge_report, not the benign NOTE orphans get.
Dependencies: pytest, calibration_records, calibration, adjudicate, label_merge (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from pathlib import Path

from calibration_records import CalibrationLabel
from calibration import (
    cohens_kappa,
    confusion_counts,
    kappa_interval,
    pre_label_confusion_counts,
    pre_label_kappa,
)
from adjudicate import apply_verdict, collect_pending
from label_merge import MergeResult, format_merge_report

_LABELLER = "claude-opus-5"
_TIMESTAMP = "2026-08-07T10:00:00+00:00"


def _label(
    i: int,
    *,
    pre_label: bool,
    scorer_verdict: bool | None = None,
    human_verdict: bool | None = None,
    needs_review: bool = False,
    prior_human_verdict: bool | None = None,
    scorer: str = "tone_judge",
) -> CalibrationLabel:
    """Build a CalibrationLabel for testing (mirrors test_calibration._label)."""
    return CalibrationLabel(
        record_id=f"case_{i:03d}:{scorer}:0",
        scorer=scorer,
        output_text=f"Output for row {i}.",
        scorer_verdict=scorer_verdict if scorer_verdict is not None else pre_label,
        pre_label=pre_label,
        pre_labeller_model=_LABELLER,
        human_verdict=human_verdict,
        adjudicated_at=_TIMESTAMP if human_verdict is not None else None,
        notes="",
        needs_review=needs_review,
        prior_human_verdict=prior_human_verdict,
    )


def _clean_and_drifted_fixture() -> list[CalibrationLabel]:
    """10 clean adjudicated rows (perfect agreement, both classes present so κ
    is well-defined — 6 all-true + 4 all-false, never all one class) + 3
    drifted rows.

    The 3 drifted rows are built to disagree with their own human_verdict
    (scorer_verdict True, human_verdict False) — if they leaked into any
    statistic below, kappa would visibly drop and the FP cell would be
    nonzero. Clean rows agree perfectly (pre_label == scorer_verdict ==
    human_verdict), so a leak is unmistakable on either axis.
    """
    clean = [_label(i, pre_label=True, human_verdict=True) for i in range(6)] + [
        _label(i, pre_label=False, human_verdict=False) for i in range(6, 10)
    ]
    drifted = [
        _label(
            100 + i,
            pre_label=True,
            scorer_verdict=True,
            human_verdict=False,
            needs_review=True,
        )
        for i in range(3)
    ]
    return clean + drifted


# ---------------------------------------------------------------------------
# RED anchor — confusion_counts excludes drifted rows and reports the count
# ---------------------------------------------------------------------------


def test_drifted_rows_are_excluded_from_kappa() -> None:
    """10 clean + 3 drifted rows report n=10, n_excluded_drifted=3, and a perfect
    headline confusion matrix — the 3 drifted disagreements never enter it."""
    rows = _clean_and_drifted_fixture()

    counts = confusion_counts(rows)
    assert counts.n == 10
    assert counts.n_excluded_drifted == 3
    assert counts.fp == 0, "a drifted row's disagreement leaked into the matrix"
    assert counts.tp == 6
    assert counts.tn == 4

    kappa = cohens_kappa(rows)
    assert kappa == 1.0, "a drifted row's disagreement leaked into kappa"


def test_drifted_rows_are_excluded_from_pre_label_axis() -> None:
    """The secondary (pre_label vs human) axis excludes drifted rows too —
    the human verdict is stale for those rows on either axis."""
    rows = _clean_and_drifted_fixture()

    counts = pre_label_confusion_counts(rows)
    assert counts.n == 10
    assert counts.n_excluded_drifted == 3
    assert counts.fp == 0

    kappa = pre_label_kappa(rows)
    assert kappa == 1.0


def test_kappa_interval_never_samples_a_drifted_row() -> None:
    """The bootstrap CI is computed only from the 10 clean rows' single cluster
    set — with zero variance among them, every resample is a perfect score."""
    rows = _clean_and_drifted_fixture()
    ci = kappa_interval(rows, resamples=200, seed=1)
    assert ci.n_rows == 10
    assert ci.lo == 1.0
    assert ci.hi == 1.0


def test_no_excluded_drift_when_nothing_has_drifted() -> None:
    """n_excluded_drifted is 0 on an ordinary fixture — the exclusion is
    additive, not a regression on the common case."""
    rows = [_label(i, pre_label=True, human_verdict=True) for i in range(5)]
    assert confusion_counts(rows).n_excluded_drifted == 0


# ---------------------------------------------------------------------------
# adjudicate.collect_pending re-surfaces drifted rows with prior context
# ---------------------------------------------------------------------------


def test_collect_pending_includes_drifted_rows() -> None:
    """A drifted row is pending even though human_verdict is already set."""
    rows = _clean_and_drifted_fixture()
    pending = collect_pending(rows)
    assert len(pending) == 3
    for row in pending:
        assert row.needs_review is True


def test_collect_pending_carries_prior_human_verdict() -> None:
    """The drifted row's prior verdict is attached so the human sees it."""
    rows = [_label(0, pre_label=True, human_verdict=False, needs_review=True)]
    pending = collect_pending(rows)
    assert len(pending) == 1
    assert pending[0].prior_human_verdict is False


def test_collect_pending_never_touched_row_has_no_prior_verdict() -> None:
    """A brand-new never-adjudicated row carries no prior_human_verdict."""
    rows = [_label(0, pre_label=True, human_verdict=None)]
    pending = collect_pending(rows)
    assert len(pending) == 1
    assert pending[0].prior_human_verdict is None


def test_reverdicting_a_drifted_row_clears_needs_review() -> None:
    """Re-adjudicating a drifted row resolves it: needs_review clears and the
    row re-enters calibration on the next call."""
    row = _label(0, pre_label=True, human_verdict=False, needs_review=True)
    updated = apply_verdict(row, "keep", _TIMESTAMP)
    assert updated.needs_review is False
    assert updated.prior_human_verdict is None

    assert collect_pending([updated]) == []
    assert confusion_counts([updated]).n_excluded_drifted == 0


def test_skipping_a_drifted_row_leaves_it_flagged() -> None:
    """Skip is a no-op — the row stays excluded and pending next time."""
    row = _label(0, pre_label=True, human_verdict=False, needs_review=True)
    updated = apply_verdict(row, "skip", _TIMESTAMP)
    assert updated.needs_review is True
    assert len(collect_pending([updated])) == 1


# ---------------------------------------------------------------------------
# label_merge.format_merge_report — drift is a WARNING, not a benign NOTE
# ---------------------------------------------------------------------------


def test_format_merge_report_prints_drift_as_warning() -> None:
    """Drifted rows render under WARNING; orphaned rows render under NOTE —
    the two must never be conflated, since one means 'a human verdict may now
    be scored against different text' and the other means 'nothing to do'."""
    result = MergeResult(
        rows=(),
        preserved=1,
        added=0,
        drifted=("case_042:tone_judge:0",),
        orphaned=(),
    )
    text = format_merge_report(result, out_path=Path("labels.jsonl"), imported=1)
    assert "WARNING" in text
    assert "case_042:tone_judge:0" in text
    assert "NOTE" not in text
