"""
Module: test_label_survival
Layer: test (unit)
Purpose: RED anchor + behaviour tests for evals/label_survival.py — the
         freeze-gate simulator that predicts which existing labels would
         drift, orphan, or survive against a candidate transcript, without
         spending a regeneration or a labelling pass.
Dependencies: pytest; eval_records, calibration_records, label_survival (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from calibration_records import CalibrationLabel
from content_hash import sha256_text
from eval_records import GenerationRecord, write_generation_dir
from label_survival import format_survival_report, simulate_survival


def _label(record_id: str, scorer: str = "tone_judge", **overrides: object) -> CalibrationLabel:
    base: dict[str, object] = dict(
        record_id=record_id,
        scorer=scorer,
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
        output_sha256="",
        criteria_sha256=sha256_text("be gruff"),
    )
    base.update(overrides)
    return CalibrationLabel(**base)  # type: ignore[arg-type]


def _record(record_id: str, criteria: str, judge_kind: str | None = "tone_judge") -> GenerationRecord:
    return GenerationRecord(
        record_id=record_id,
        source="runner",
        npc_id="mira_innkeeper",
        player_id="player_1",
        player_message="where are the troops",
        npc_response="a gruff reply",
        criteria=criteria,
        judge_kind=judge_kind,  # type: ignore[arg-type]
        expected_polarity="pass_on_yes",
    )


def _write_transcript(tmp_path: Path, records: list[GenerationRecord]) -> Path:
    gen_dir = tmp_path / "gen"
    write_generation_dir(gen_dir, records, gen_id="test_gen", k=1)
    return gen_dir / "outputs.jsonl"


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_criteria_change_is_reported_as_drift_not_survival(tmp_path: Path) -> None:
    """A record whose criteria text changed must be classified 'drifts', not 'survives'.

    Without the fix (naive equality on record_id alone, or no hash comparison
    at all): a criteria edit that doesn't touch record_id or scorer is
    invisible to the simulator and a labelling pass proceeds against
    unlabelled-drifted content believing the corpus is frozen.
    """
    existing = _label("case_x:tone_judge:0#r0", criteria_sha256=sha256_text("be gruff"))
    transcript = _write_transcript(
        tmp_path, [_record("case_x:tone_judge:0", criteria="be warm and gentle")]
    )
    report = simulate_survival([existing], transcript)
    assert ("case_x:tone_judge:0#r0", "tone_judge") in report.drifts
    assert report.is_frozen is False


# ---------------------------------------------------------------------------
# Behaviour tests
# ---------------------------------------------------------------------------


def test_unchanged_criteria_survives(tmp_path: Path) -> None:
    """Identical criteria between label and transcript classifies as survives."""
    existing = _label("case_x:tone_judge:0#r0", criteria_sha256=sha256_text("be gruff"))
    transcript = _write_transcript(tmp_path, [_record("case_x:tone_judge:0", criteria="be gruff")])
    report = simulate_survival([existing], transcript)
    assert ("case_x:tone_judge:0#r0", "tone_judge") in report.survives
    assert report.drifts == ()
    assert report.orphaned == ()
    assert report.is_frozen is True


def test_missing_from_transcript_is_orphaned_not_drifted(tmp_path: Path) -> None:
    """A label with no matching transcript row is orphaned, distinct from drift."""
    existing = _label("case_gone:tone_judge:0#r0", criteria_sha256=sha256_text("be gruff"))
    transcript = _write_transcript(tmp_path, [_record("case_x:tone_judge:0", criteria="be gruff")])
    report = simulate_survival([existing], transcript)
    assert ("case_gone:tone_judge:0#r0", "tone_judge") in report.orphaned
    assert report.drifts == ()
    # orphaned rows still count against is_frozen — a case rename is worth surfacing
    assert report.is_frozen is False


def test_new_transcript_row_with_no_existing_label(tmp_path: Path) -> None:
    """A transcript row with no matching label is 'new' and does not affect is_frozen."""
    transcript = _write_transcript(tmp_path, [_record("case_new:tone_judge:0", criteria="be gruff")])
    report = simulate_survival([], transcript)
    assert ("case_new:tone_judge:0#r0", "tone_judge") in report.new
    assert report.is_frozen is True  # nothing existing was invalidated


def test_empty_stored_hash_never_reported_as_drift(tmp_path: Path) -> None:
    """Rows written before content-addressing existed (empty criteria_sha256)
    must not be reported as drifted (DEC-181's own rule for _has_drifted)."""
    existing = _label("case_legacy:tone_judge:0#r0", criteria_sha256="")
    transcript = _write_transcript(
        tmp_path, [_record("case_legacy:tone_judge:0", criteria="anything at all")]
    )
    report = simulate_survival([existing], transcript)
    assert ("case_legacy:tone_judge:0#r0", "tone_judge") in report.survives
    assert report.is_frozen is True


def test_format_survival_report_names_drifted_and_orphaned_keys(tmp_path: Path) -> None:
    """The rendered report must name specific keys, not just counts — the whole
    point is that a stale claim of 'frozen' is checkable, not a silent count."""
    existing = _label("case_x:tone_judge:0#r0", criteria_sha256=sha256_text("be gruff"))
    transcript = _write_transcript(
        tmp_path, [_record("case_x:tone_judge:0", criteria="totally different criteria")]
    )
    report = simulate_survival([existing], transcript)
    text = format_survival_report(report)
    assert "case_x:tone_judge:0#r0" in text
    assert "NOT FROZEN" in text


def test_real_labels_file_survives_its_own_transcript() -> None:
    """Sanity check against the real committed artifact: labelling and generation
    are in sync today, so simulating against the transcript they came from
    must show zero drift and zero orphaning.

    Filtered to gen_id="k3_73e6c36": the shared labels_v1.jsonl now also carries
    354 rows for k3_61b01dad_negadv (merged 2026-09-05), which are correctly
    orphaned against THIS transcript — they belong to a different one. This test
    is about k3_73e6c36's own labels staying in sync with k3_73e6c36's own
    transcript, not about every generation ever merged into the shared file."""
    repo_root = Path(__file__).resolve().parents[3]
    labels_path = repo_root / "evals" / "calibration" / "labels_v1.jsonl"
    transcript_path = repo_root / "evals" / "generations" / "k3_73e6c36" / "outputs.jsonl"
    if not labels_path.exists() or not transcript_path.exists():
        pytest.skip("real committed artifact not present in this checkout")

    from calibration_records import read_calibration_labels

    labels = [r for r in read_calibration_labels(labels_path) if r.gen_id == "k3_73e6c36"]
    report = simulate_survival(labels, transcript_path)
    assert report.drifts == ()
    assert report.orphaned == ()
