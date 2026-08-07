"""
Module: test_judged_records
Layer: test (unit)
Purpose: Tests for --json-out JSONL persistence in judge_runner.main (EVAL-P1.6).
Dependencies: json, pathlib, unittest.mock; judge_runner, eval_records, matchers (evals/).
Used by: pytest (make test / make check).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import judge_runner
from eval_records import GenerationRecord, write_transcript
from matchers import JudgeResult

_RECORD_COUNT = 6
_JUDGE_KIND = "tone_judge"
_JUDGE_MODEL_SENTINEL = "mixtral-test:sentinel"


def _make_record(i: int, *, judge_kind: str | None = _JUDGE_KIND) -> GenerationRecord:
    """Build a minimal GenerationRecord fixture for judge_runner tests."""
    return GenerationRecord(
        record_id=f"case_{i:02d}:{judge_kind}:0" if judge_kind else f"case_{i:02d}:none:0",
        source="runner",
        npc_id="mira_innkeeper",
        player_id="test_player",
        player_message="hello",
        npc_response="Hello there!",
        criteria="Is the tone warm?",
        judge_kind=judge_kind,
        expected_polarity="pass_on_yes",
        repetition=i % 3,
        duration_ms=42,
    )


def _write_fixture_transcript(tmp_path: Path, count: int = _RECORD_COUNT) -> Path:
    """Write a v2 transcript with ``count`` tone_judge records to tmp_path."""
    records = [_make_record(i) for i in range(count)]
    path = tmp_path / "transcript.json"
    write_transcript(path, records)
    return path


def test_json_out_writes_one_row_per_judged_record(tmp_path: Path) -> None:
    """main writes exactly one JSONL row per judged record when --json-out is given.

    Confirms: row count, required field names, non-empty judge_model on every row,
    and that score/passed values survive the round-trip.
    """
    transcript_path = _write_fixture_transcript(tmp_path)
    jsonl_path = tmp_path / "judged.jsonl"

    mock_result = JudgeResult(score=True, error="")
    with (
        patch("matchers._run_binary_judge", return_value=mock_result),
        patch("judge_config.resolve_judge_model", return_value=_JUDGE_MODEL_SENTINEL),
    ):
        exit_code = judge_runner.main(
            ["--transcript", str(transcript_path), "--json-out", str(jsonl_path)]
        )

    assert exit_code == 0, f"Expected exit 0, got {exit_code}"
    assert jsonl_path.exists(), "--json-out path was not created"

    lines = [l for l in jsonl_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == _RECORD_COUNT, (
        f"Expected {_RECORD_COUNT} JSONL rows, got {len(lines)}"
    )

    required_keys = {
        "record_id",
        "case_id",
        "judge_kind",
        "passed",
        "score",
        "detail",
        "judge_model",
        "repetition",
    }
    for raw in lines:
        row = json.loads(raw)
        missing = required_keys - row.keys()
        assert not missing, f"JSONL row missing keys: {missing}"
        assert row["judge_model"], "judge_model must be non-empty on every row"
        assert row["judge_kind"] == _JUDGE_KIND
        assert row["passed"] is True
        assert row["score"] is True


def test_json_out_round_trips_judged_record_fields(tmp_path: Path) -> None:
    """Each JSONL row carries record_id, case_id (derived), repetition, and detail."""
    transcript_path = _write_fixture_transcript(tmp_path, count=2)
    jsonl_path = tmp_path / "judged.jsonl"

    mock_result = JudgeResult(score=False, error="NPC tone was cold")
    with (
        patch("matchers._run_binary_judge", return_value=mock_result),
        patch("judge_config.resolve_judge_model", return_value=_JUDGE_MODEL_SENTINEL),
    ):
        judge_runner.main(
            ["--transcript", str(transcript_path), "--json-out", str(jsonl_path)]
        )

    rows = [json.loads(l) for l in jsonl_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 2

    row0 = rows[0]
    # case_id is the prefix of record_id before the last two colon-segments
    assert row0["case_id"] == "case_00"
    assert row0["record_id"] == "case_00:tone_judge:0"
    assert row0["detail"] == "NPC tone was cold"
    assert row0["judge_model"] == _JUDGE_MODEL_SENTINEL
    assert row0["repetition"] == 0

    row1 = rows[1]
    assert row1["case_id"] == "case_01"
    assert row1["repetition"] == 1


def test_infra_failure_writes_null_score_and_is_not_silently_dropped(tmp_path: Path) -> None:
    """An infra failure produces passed=false, score=null and is never silently dropped.

    score=null is distinguishable from a genuine fail (score=false, passed=false).
    Both the failure row and the passing row appear in the JSONL output.
    """
    transcript_path = _write_fixture_transcript(tmp_path, count=2)
    jsonl_path = tmp_path / "judged.jsonl"

    results = [
        JudgeResult(score=True, error=""),
        JudgeResult(score=None, error="infra_failure"),
    ]
    mock_judge = MagicMock(side_effect=results)

    with (
        patch("matchers._run_binary_judge", mock_judge),
        patch("judge_config.resolve_judge_model", return_value=_JUDGE_MODEL_SENTINEL),
    ):
        judge_runner.main(
            ["--transcript", str(transcript_path), "--json-out", str(jsonl_path)]
        )

    rows = [json.loads(l) for l in jsonl_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 2, "Infra failure row must not be silently dropped"

    passing_row = rows[0]
    assert passing_row["score"] is True
    assert passing_row["passed"] is True

    infra_row = rows[1]
    assert infra_row["score"] is None, "Infra failure must write score=null"
    assert infra_row["passed"] is False, "Infra failure must write passed=false"
    # Distinguish from genuine fail: genuine fail has score=false, infra has score=null
    assert infra_row["score"] is not False, "Infra failure score must be null, not false"
