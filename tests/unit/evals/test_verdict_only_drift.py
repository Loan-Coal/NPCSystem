"""
Module: test_verdict_only_drift
Layer: test (unit)
Purpose: Regression tests for evals/label_merge.py's _has_drifted drift
         definition. Originally the RED anchor for EVAL-P20.3a Step 3
         (ISSUE-160: a scorer_verdict flip on hash-identical content was
         invisible to needs_review). EVAL-P20.3b (DEC-181, AskUserQuestion
         option (d)) superseded that fix: drift is now defined as
         criteria_sha256 changing ONLY — output_text and scorer_verdict no
         longer participate. The tests below were updated in that same
         commit to assert the current (superseding) behavior, not reverted
         silently — see the module docstring note on each changed test.
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
# EVAL-P20.3b (DEC-181): scorer_verdict and output_sha256 no longer drift
# ---------------------------------------------------------------------------


def test_verdict_only_change_is_no_longer_drift() -> None:
    """EVAL-P20.3b (DEC-181): a scorer_verdict flip alone is NOT drift.

    Superseded EVAL-P20.3a Step 3's `test_verdict_only_drift_flags_needs_review`,
    which asserted the opposite. EVAL-P20.3a Step 3 (ISSUE-160) made a
    scorer_verdict flip flag needs_review; EVAL-P20.3b redefines drift as
    criteria_sha256-only (option (d), chosen via AskUserQuestion) — ordinary
    LLM judge non-determinism (no seed exists for judge calls, DEC-146) no
    longer invalidates a stored human_verdict by itself.
    """
    existing = _label(scorer_verdict=True)
    incoming = _label(scorer_verdict=False)
    assert _has_drifted(existing, incoming) is False


def test_output_hash_change_alone_is_no_longer_drift() -> None:
    """EVAL-P20.3b (DEC-181): an output_sha256 change alone is NOT drift.

    Superseded `test_hash_drift_alone_is_still_detected`. Trust now follows
    criteria_sha256 only (ISSUE-168 rescope) — DEC-176 measured byte-identical
    reproduction as low as 4.2% at the shipped max_tokens=512, so an
    output-text trust policy invalidated ~295 rows on every regeneration by
    design, regardless of whether the NPC's answer changed in substance.
    """
    existing = _label(output_sha256="abc123")
    incoming = _label(output_sha256="different")
    assert _has_drifted(existing, incoming) is False


def test_criteria_hash_change_is_still_drift() -> None:
    """A criteria_sha256 change is drift — the one signal EVAL-P20.3b keeps."""
    existing = _label(criteria_sha256="def456")
    incoming = _label(criteria_sha256="different-criteria-hash")
    assert _has_drifted(existing, incoming) is True


def test_nothing_changed_is_not_drift() -> None:
    """Nothing changed → not drifted (unaffected by the redefinition)."""
    existing = _label()
    incoming = _label()
    assert _has_drifted(existing, incoming) is False


def test_merge_does_not_flag_needs_review_on_verdict_only_change() -> None:
    """merge_labels keeps the row clean when only scorer_verdict changed.

    Superseded `test_merge_flags_needs_review_on_verdict_only_drift`.
    """
    existing = _label(scorer_verdict=True, human_verdict=True)
    incoming = _label(scorer_verdict=False)
    result = merge_labels([existing], [incoming])
    merged = result.rows[0]
    assert merged.needs_review is False
    assert existing.record_id not in result.drifted


def test_merge_flags_needs_review_on_criteria_drift() -> None:
    """merge_labels still flags needs_review when the criteria itself changed."""
    existing = _label(criteria_sha256="def456", human_verdict=True)
    incoming = _label(criteria_sha256="different-criteria-hash")
    result = merge_labels([existing], [incoming])
    merged = result.rows[0]
    assert merged.needs_review is True
    assert existing.record_id in result.drifted


def test_format_merge_report_states_the_current_drift_definition() -> None:
    """The report states drift means 'criteria changed', not output text.

    Superseded `test_format_merge_report_states_drift_definition`, which
    asserted the EVAL-P20.3a Step 3 wording ("output/criteria hash changed,
    or scorer_verdict changed").
    """
    existing = _label(criteria_sha256="def456", human_verdict=True)
    incoming = _label(criteria_sha256="different-criteria-hash")
    result = merge_labels([existing], [incoming])
    report = format_merge_report(result, Path("out.jsonl"), imported=1)
    assert "criteria changed" in report
    assert "output_text is no longer part of the drift definition" in report
