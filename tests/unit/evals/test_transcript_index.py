"""
Module: test_transcript_index
Layer: test (unit)
Purpose: Unit tests for transcript_index.py — building item_id-keyed indexes from
         a generation transcript (ExportItem, carrying criteria/observed/
         player_message/output_text) and a judged.jsonl (scorer_verdict), for
         label_import's join step.
Dependencies: json, pathlib, pytest, eval_records, export_item, transcript_index (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import json
from pathlib import Path

from eval_records import GenerationRecord, write_generation_dir
from export_item import ExportItem
from record_identity import composite_item_id
from transcript_index import build_judged_index, build_transcript_index

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_JUDGE_RECORD = GenerationRecord(
    record_id="case_001_grieving_elder:tone_judge:0",
    source="runner",
    npc_id="vw_elder",
    player_id="player_1",
    player_message="My son died in the war.",
    npc_response="I'm sorry for your loss.",
    criteria="Respond with warmth and empathy.",
    judge_kind="tone_judge",
    matcher_kind=None,
    expected_polarity="pass_on_yes",
)

_DETERMINISTIC_RECORD = GenerationRecord(
    record_id="case_002_suspicious_guard:in_set:0",
    source="runner",
    npc_id="vw_guard",
    player_id="player_1",
    player_message="What did you see, guard?",
    npc_response="I saw nothing unusual.",
    criteria="",
    judge_kind=None,
    matcher_kind="in_set",
    expected_polarity="pass_on_yes",
    metadata={
        "expectation": {"field": "facial_expression.type", "values": ["neutral", "grim"]},
        "response": {"facial_expression": {"type": "neutral", "intensity": 0}},
    },
)


# ---------------------------------------------------------------------------
# Tests — build_transcript_index
# ---------------------------------------------------------------------------


def test_build_transcript_index_populates_criteria_for_judge_record(tmp_path: Path) -> None:
    """A judge-kind record's ExportItem carries its verbatim criteria string."""
    write_generation_dir(tmp_path, [_JUDGE_RECORD], gen_id="test", k=1)
    index = build_transcript_index(tmp_path / "outputs.jsonl")
    key = composite_item_id(_JUDGE_RECORD.record_id, 0)
    assert key in index
    item = index[key]
    assert isinstance(item, ExportItem)
    assert item.criteria == "Respond with warmth and empathy."
    assert item.output_text == "I'm sorry for your loss."
    assert item.player_message == "My son died in the war."


def test_build_transcript_index_populates_criteria_for_deterministic_record(tmp_path: Path) -> None:
    """A deterministic record's ExportItem carries criteria rendered from its expectation."""
    write_generation_dir(tmp_path, [_DETERMINISTIC_RECORD], gen_id="test", k=1)
    index = build_transcript_index(tmp_path / "outputs.jsonl")
    key = composite_item_id(_DETERMINISTIC_RECORD.record_id, 0)
    item = index[key]
    assert item.criteria != ""
    assert "facial_expression.type" in item.criteria


def test_build_transcript_index_populates_observed_for_in_set_record(tmp_path: Path) -> None:
    """An in_set record's ExportItem carries the observed response field being judged."""
    write_generation_dir(tmp_path, [_DETERMINISTIC_RECORD], gen_id="test", k=1)
    index = build_transcript_index(tmp_path / "outputs.jsonl")
    key = composite_item_id(_DETERMINISTIC_RECORD.record_id, 0)
    item = index[key]
    assert item.observed == {"facial_expression.type": "neutral"}


# ---------------------------------------------------------------------------
# Tests — build_judged_index
# ---------------------------------------------------------------------------


def test_build_judged_index_maps_composite_id_to_verdict(tmp_path: Path) -> None:
    """build_judged_index keys verdicts by the repetition-qualified item id."""
    judged_path = tmp_path / "judged.jsonl"
    lines = [
        json.dumps({"record_id": "case_001:tone_judge:0", "repetition": 0, "passed": True}),
        json.dumps({"record_id": "case_002:tone_judge:0", "repetition": 1, "passed": False}),
    ]
    judged_path.write_text("\n".join(lines), encoding="utf-8")
    index = build_judged_index(judged_path)
    assert index[composite_item_id("case_001:tone_judge:0", 0)] is True
    assert index[composite_item_id("case_002:tone_judge:0", 1)] is False
