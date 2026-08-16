"""
Module: test_verdict_only_drift
Layer: test (unit)
Purpose: RED anchor for EVAL-P20.3a Step 3 (ISSUE-160) — evals/label_merge.py's
         _has_drifted must also flag a scorer_verdict change on hash-identical
         output/criteria as drift, and format_merge_report must state the drift
         definition explicitly rather than leaving "0 drifted" ambiguous between
         "byte-identical" and "nothing about this row changed".
Dependencies: pytest, label_merge, calibration_records (evals/)
Used by: pytest (make test / make check)
"""
from __future__ import annotations

from pathlib import Path

from calibration_records import CalibrationLabel
from label_merge import _has_drifted, format_merge_report, merge_labels


def _label(**overrides: object) -> CalibrationLabel:
    """Build a CalibrationLabel for the real case named in ISSUE-160."""
    base: dict[str, object] = dict(
        record_id="case_adv_lira_troop_positions:tone_judge:4#r0",
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


def test_verdict_only_drift_flags_needs_review() -> None:
    """A scorer_verdict flip on byte-identical output/criteria hashes is drift.

    Real case: case_adv_lira_troop_positions:tone_judge:4#r0 flipped
    scorer_verdict true->false on re-judge with output_sha256/criteria_sha256
    both byte-identical old vs new (ordinary LLM judge non-determinism,
    DEC-146). Before the fix, _has_drifted only compares the two hashes, so
    this is invisible to needs_review.
    """
    existing = _label(scorer_verdict=True)
    incoming = _label(scorer_verdict=False)
    assert _has_drifted(existing, incoming) is True


# ---------------------------------------------------------------------------
# Behaviour tests
# ---------------------------------------------------------------------------


def test_hash_and_verdict_unchanged_is_not_drift() -> None:
    """Nothing changed → not drifted."""
    existing = _label(scorer_verdict=True)
    incoming = _label(scorer_verdict=True)
    assert _has_drifted(existing, incoming) is False


def test_hash_drift_alone_is_still_detected() -> None:
    """The pre-existing hash-drift path must keep working unchanged."""
    existing = _label(output_sha256="abc123")
    incoming = _label(output_sha256="different")
    assert _has_drifted(existing, incoming) is True


def test_merge_flags_needs_review_on_verdict_only_drift() -> None:
    """merge_labels flags the row needs_review even though both hashes match."""
    existing = _label(scorer_verdict=True, human_verdict=True)
    incoming = _label(scorer_verdict=False)
    result = merge_labels([existing], [incoming])
    merged = result.rows[0]
    assert merged.needs_review is True
    assert existing.record_id in result.drifted


def test_format_merge_report_states_drift_definition() -> None:
    """The report states what 'drifted' means, not just a bare count.

    Before this fix, "0 drifted" was ambiguous between "byte-identical" and
    "nothing about this row changed" — ISSUE-160 was filed because a real
    scorer_verdict flip was invisible under exactly that ambiguity.
    """
    existing = _label(scorer_verdict=True, human_verdict=True)
    incoming = _label(scorer_verdict=False)
    result = merge_labels([existing], [incoming])
    report = format_merge_report(result, Path("out.jsonl"), imported=1)
    assert "output/criteria hash" in report
    assert "scorer_verdict" in report
