"""
test_eval_records.py - Unit tests for evals/eval_records.py.

Covers:
- GenerationRecord round-trips through write_transcript/read_transcript
- read_transcript raises ValidationError on schema mismatch
- judge_kind=None is a valid GenerationRecord
- Invalid expected_polarity raises ValidationError
- JudgedRecord carries score + passed + reasoning
- TranscriptFile version defaults to 1
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

# evals/ is on pytest pythonpath (pyproject.toml pythonpath = [..., "evals"])
from eval_records import (
    GenerationRecord,
    JudgedRecord,
    TranscriptFile,
    read_transcript,
    write_transcript,
)

_BASE_FIELDS: dict = {
    "record_id": "test_case:tone_judge:0",
    "source": "runner",
    "npc_id": "npc_eval",
    "player_id": "player_eval",
    "player_message": "What news from the north?",
    "npc_response": "Soldiers march, the roads are dangerous.",
    "criteria": "Answer YES if the response is substantive and in-character.",
    "judge_kind": "tone_judge",
    "expected_polarity": "pass_on_yes",
}


def test_generation_record_round_trip(tmp_path: Path) -> None:
    record = GenerationRecord(**_BASE_FIELDS)
    path = tmp_path / "transcript.json"
    write_transcript(path, [record])
    tf = read_transcript(path)
    assert len(tf.records) == 1
    loaded = tf.records[0]
    assert loaded.record_id == _BASE_FIELDS["record_id"]
    assert loaded.npc_response == _BASE_FIELDS["npc_response"]
    assert loaded.judge_kind == "tone_judge"
    assert loaded.expected_polarity == "pass_on_yes"


def test_schema_mismatch_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        '{"version": 1, "generated_at": "2026-01-01T00:00:00+00:00", "records": [{"bad_field": 1}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        read_transcript(path)


def test_judge_kind_none_allowed() -> None:
    record = GenerationRecord(**{**_BASE_FIELDS, "judge_kind": None})
    assert record.judge_kind is None


def test_polarity_literal_enforced() -> None:
    with pytest.raises(ValidationError):
        GenerationRecord(**{**_BASE_FIELDS, "expected_polarity": "invalid_polarity"})


def test_source_literal_enforced() -> None:
    with pytest.raises(ValidationError):
        GenerationRecord(**{**_BASE_FIELDS, "source": "bad_source"})


def test_judged_record_fields() -> None:
    record = GenerationRecord(**_BASE_FIELDS)
    judged = JudgedRecord(**record.model_dump(), passed=True, score=True, reasoning="sounds good")
    assert judged.passed is True
    assert judged.score is True
    assert judged.reasoning == "sounds good"
    assert judged.record_id == _BASE_FIELDS["record_id"]


def test_judged_record_score_none_allowed() -> None:
    record = GenerationRecord(**_BASE_FIELDS)
    judged = JudgedRecord(**record.model_dump(), passed=False, score=None, reasoning="infra_failure")
    assert judged.score is None


def test_transcript_file_version_defaults_to_one() -> None:
    tf = TranscriptFile(generated_at="2026-06-23T00:00:00+00:00", records=())
    assert tf.version == 1
    assert tf.records == ()


def test_multiple_records_round_trip(tmp_path: Path) -> None:
    records = [
        GenerationRecord(**_BASE_FIELDS),
        GenerationRecord(**{
            **_BASE_FIELDS,
            "record_id": "test_case:affirms_judge:1",
            "judge_kind": "affirms_judge",
            "expected_polarity": "pass_on_no",
        }),
        GenerationRecord(**{
            **_BASE_FIELDS,
            "record_id": "ah_case:refusal_judge:0",
            "source": "anti_hallucination",
            "judge_kind": "refusal_judge",
            "expected_polarity": "pass_on_yes",
        }),
    ]
    path = tmp_path / "multi.json"
    write_transcript(path, records)
    tf = read_transcript(path)
    assert len(tf.records) == 3
    assert tf.records[1].expected_polarity == "pass_on_no"
    assert tf.records[2].source == "anti_hallucination"


def test_metadata_field_persists(tmp_path: Path) -> None:
    record = GenerationRecord(**{**_BASE_FIELDS, "metadata": {"substrings": ["war", "north"]}})
    path = tmp_path / "meta.json"
    write_transcript(path, [record])
    tf = read_transcript(path)
    assert tf.records[0].metadata == {"substrings": ["war", "north"]}


def test_active_conditions_round_trip(tmp_path: Path) -> None:
    record = GenerationRecord(**{**_BASE_FIELDS, "active_conditions": ("northern_war_begins",)})
    path = tmp_path / "conds.json"
    write_transcript(path, [record])
    tf = read_transcript(path)
    assert "northern_war_begins" in tf.records[0].active_conditions
