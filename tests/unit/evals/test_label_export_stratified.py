"""
Module: test_label_export_stratified
Layer: test (unit)
Purpose: End-to-end tests for the label-export-stratified CLI verb — the
         projected-yield report prints before anything is written, a judge
         whose ceiling clears DEC-260's floor gets an oversampled batch, and a
         judge whose ceiling cannot clear it gets no batch and a non-zero exit.
Dependencies: pytest; calibration_records, eval_records, label_export_stratified
         (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from pathlib import Path

from calibration_records import write_calibration_labels
from eval_records import GenerationRecord, write_generation_dir
from label_export_stratified import main


def _record(case_id: str, kind: str, judge_kind: str | None = None, matcher_kind: str | None = None) -> GenerationRecord:
    return GenerationRecord(
        record_id=f"{case_id}:{kind}:0",
        source="runner",
        npc_id="npc_a",
        player_id="player_eval",
        player_message="hi",
        npc_response="an answer",
        criteria="answer yes",
        judge_kind=judge_kind,  # type: ignore[arg-type]
        matcher_kind=matcher_kind,  # type: ignore[arg-type]
        expected_polarity="pass_on_yes",
    )


def _write_transcript(tmp_path: Path, records: list[GenerationRecord]) -> Path:
    gen_dir = tmp_path / "gen"
    write_generation_dir(gen_dir, records, gen_id="test_gen", k=1)
    return gen_dir / "outputs.jsonl"


def _write_strata(tmp_path: Path, negative_cases: list[str]) -> Path:
    strata_file = tmp_path / "case_strata.yaml"
    body = "\n".join(f"  - {c}" for c in negative_cases)
    strata_file.write_text(f"expected_negative_cases:\n{body}\n", encoding="utf-8")
    return strata_file


def _write_empty_labels(tmp_path: Path) -> Path:
    labels_path = tmp_path / "labels.jsonl"
    write_calibration_labels(labels_path, [])
    return labels_path


def test_a_judge_that_clears_the_floor_gets_a_batch(tmp_path: Path) -> None:
    negative_cases = [f"case_neg_{i:03d}" for i in range(30)]
    records = [_record(cid, "commits_judge", judge_kind="commits_judge") for cid in negative_cases]
    transcript = _write_transcript(tmp_path, records)
    strata = _write_strata(tmp_path, negative_cases)
    labels = _write_empty_labels(tmp_path)
    out_dir = tmp_path / "out"

    exit_code = main(
        [
            "--transcript", str(transcript),
            "--out-dir", str(out_dir),
            "--labels", str(labels),
            "--strata", str(strata),
            "--scorer", "commits_judge",
        ]
    )
    assert exit_code == 0
    batch_file = out_dir / "commits_judge" / "batch_001.json"
    assert batch_file.exists()


def test_a_judge_below_the_floor_gets_no_batch_and_nonzero_exit(tmp_path: Path) -> None:
    # Only 3 negative candidates — nowhere near the 25-minority floor.
    negative_cases = [f"case_neg_{i:03d}" for i in range(3)]
    records = [_record(cid, "tone_judge", judge_kind="tone_judge") for cid in negative_cases]
    transcript = _write_transcript(tmp_path, records)
    strata = _write_strata(tmp_path, negative_cases)
    labels = _write_empty_labels(tmp_path)
    out_dir = tmp_path / "out"

    exit_code = main(
        [
            "--transcript", str(transcript),
            "--out-dir", str(out_dir),
            "--labels", str(labels),
            "--strata", str(strata),
            "--scorer", "tone_judge",
        ]
    )
    assert exit_code == 1
    assert not (out_dir / "tone_judge").exists()


def test_a_passing_judge_still_gets_its_batch_when_another_judge_is_refused(tmp_path: Path) -> None:
    """One judge failing must not block a different judge that clears the floor."""
    ok_cases = [f"case_neg_{i:03d}" for i in range(30)]
    bad_cases = [f"case_adv_{i:03d}" for i in range(2)]
    records = [_record(cid, "commits_judge", judge_kind="commits_judge") for cid in ok_cases] + [
        _record(cid, "affirms_judge", judge_kind="affirms_judge") for cid in bad_cases
    ]
    transcript = _write_transcript(tmp_path, records)
    strata = _write_strata(tmp_path, ok_cases + bad_cases)
    labels = _write_empty_labels(tmp_path)
    out_dir = tmp_path / "out"

    exit_code = main(
        [
            "--transcript", str(transcript),
            "--out-dir", str(out_dir),
            "--labels", str(labels),
            "--strata", str(strata),
            "--scorer", "commits_judge",
            "--scorer", "affirms_judge",
        ]
    )
    assert exit_code == 1
    assert (out_dir / "commits_judge" / "batch_001.json").exists()
    assert not (out_dir / "affirms_judge").exists()
