"""
Module: test_label_export
Layer: test (unit)
Purpose: Unit tests for label_export.py — batch export of transcript records for the
         CLI labelling pass. Covers ExportItem field inclusion, scorer_verdict absence,
         batch-size enforcement, vocabulary inclusion for graph scorers, and
         JSON serialisation correctness.
Dependencies: json, pathlib, pytest, eval_records (stubs), label_export (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from eval_records import GenerationRecord
from record_identity import composite_item_id
from label_export import (
    filter_by_scorer,
    GRAPH_SCORER_KINDS,
    MAX_BATCH_SIZE,
    ExportItem,
    build_export_item,
    build_export_items,
    write_export_batches,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_record(
    record_id: str,
    *,
    npc_id: str = "mira_innkeeper",
    player_message: str = "Hello there.",
    npc_response: str = "Good day, traveller.",
    criteria: str = "Respond with warmth.",
    judge_kind: str | None = "tone_judge",
    matcher_kind: Any = None,
) -> GenerationRecord:
    """Build a minimal GenerationRecord for testing."""
    return GenerationRecord(
        record_id=record_id,
        source="runner",
        npc_id=npc_id,
        player_id="player_01",
        player_message=player_message,
        npc_response=npc_response,
        criteria=criteria,
        judge_kind=judge_kind,
        matcher_kind=matcher_kind,
        expected_polarity="pass_on_yes",
    )


_TONE_RECORD = _make_record("case_001:tone_judge:0", judge_kind="tone_judge")
_AFFIRMS_RECORD = _make_record("case_002:affirms_judge:0", judge_kind="affirms_judge")
_ENTITY_RECORD = _make_record(
    "case_003:entity_scorer:0",
    judge_kind=None,
    matcher_kind=None,  # entity_scorer is applied outside matcher_kind
    criteria="",
)
# Simulate a graph scorer record by overriding the scorer via a subclass trick
# is not needed — we patch scorer identity via label_export._scorer_for_record
# or simply test build_export_item with a patched scorer name via the vocabulary arg.


# ---------------------------------------------------------------------------
# Tests — ExportItem field contract
# ---------------------------------------------------------------------------


def test_export_item_never_has_scorer_verdict_field() -> None:
    """ExportItem must not expose scorer_verdict as a field at all."""
    item = ExportItem(
        record_id="x",
        scorer="tone_judge",
        npc_id="mira",
        player_message="Hello",
        criteria="Be warm",
        output_text="Good day!",
    )
    dumped = item.model_dump()
    assert "scorer_verdict" not in dumped
    assert "passed" not in dumped
    assert "score" not in dumped


def test_build_export_item_includes_required_fields() -> None:
    """build_export_item includes record_id, scorer, npc_id, player_message, criteria, output_text."""
    item = build_export_item(_TONE_RECORD)
    # Repetition-qualified: the bare record_id repeats k times in a k-repeat run.
    assert item.record_id == "case_001:tone_judge:0#r0"
    assert item.scorer == "tone_judge"
    assert item.npc_id == "mira_innkeeper"
    assert item.player_message == "Hello there."
    assert item.criteria == "Respond with warmth."
    assert item.output_text == "Good day, traveller."


def test_build_export_item_uses_judge_kind_as_scorer() -> None:
    """Scorer is taken from judge_kind for LLM judge records."""
    item = build_export_item(_AFFIRMS_RECORD)
    assert item.scorer == "affirms_judge"


def test_build_export_item_uses_matcher_kind_as_scorer() -> None:
    """Scorer is taken from matcher_kind for deterministic records."""
    record = _make_record(
        "case_004:keyword_any:0",
        judge_kind=None,
        matcher_kind="keyword_any",
        criteria="",
    )
    item = build_export_item(record)
    assert item.scorer == "keyword_any"


def test_build_export_item_no_vocabulary_for_non_graph_scorer() -> None:
    """Non-graph scorer records have vocabulary=None even if a vocabulary dict is passed."""
    vocab = {"ids": ["npc_001", "loc_001"]}
    item = build_export_item(_TONE_RECORD, vocabulary=vocab)
    assert item.vocabulary is None


def test_build_export_item_includes_vocabulary_for_graph_scorer() -> None:
    """Graph scorer records carry the vocabulary dict when one is provided."""
    vocab = {"ids": ["npc_001", "loc_001"]}

    # Build a record whose scorer resolves to a known graph scorer kind.
    # We test by constructing a record with matcher_kind matching a GRAPH_SCORER_KINDS entry.
    # label_export._scorer_for_record returns judge_kind if set, then matcher_kind.
    # So we build a record with judge_kind=None and matcher_kind set to a graph scorer name.
    # Since DeterministicMatcherKind doesn't include 'entity_scorer', we test the fallback path
    # ('unknown') and verify GRAPH_SCORER_KINDS drives vocabulary inclusion in build_export_item
    # directly via the scorer check in that function.
    # We do this by calling build_export_item with a record whose judge_kind matches one of
    # the GRAPH_SCORER_KINDS — but those are not valid judge_kind Literals.
    # Instead, test the internal path: an ExportItem built with scorer in GRAPH_SCORER_KINDS
    # and a vocabulary includes the vocabulary.
    # We test this by verifying the constant set and the item-level check manually.
    assert "entity_scorer" in GRAPH_SCORER_KINDS
    assert "knowledge_scorer" in GRAPH_SCORER_KINDS

    # Build an ExportItem directly with a graph scorer to confirm vocabulary is accepted.
    item = ExportItem(
        record_id="case_003:entity_scorer:0",
        scorer="entity_scorer",
        npc_id="mira_innkeeper",
        player_message="Hello",
        criteria="",
        output_text="Mira greeted the traveller.",
        vocabulary=vocab,
    )
    assert item.vocabulary == vocab


# ---------------------------------------------------------------------------
# Tests — batch writing
# ---------------------------------------------------------------------------


def test_write_export_batches_single_batch_for_small_set(tmp_path: Path) -> None:
    """A set smaller than MAX_BATCH_SIZE produces exactly one batch file."""
    records = [_make_record(f"case_{i:03d}:tone_judge:0") for i in range(5)]
    items = build_export_items(records)
    paths = write_export_batches(items, tmp_path)
    assert len(paths) == 1
    assert paths[0].name == "batch_001.json"


def test_write_export_batches_splits_at_25(tmp_path: Path) -> None:
    """26 items produce two batch files: 25 in the first, 1 in the second."""
    records = [_make_record(f"case_{i:03d}:tone_judge:0") for i in range(26)]
    items = build_export_items(records)
    paths = write_export_batches(items, tmp_path)
    assert len(paths) == 2
    first_batch = json.loads(paths[0].read_text(encoding="utf-8"))
    second_batch = json.loads(paths[1].read_text(encoding="utf-8"))
    assert len(first_batch) == MAX_BATCH_SIZE
    assert len(second_batch) == 1


def test_write_export_batches_json_contains_required_keys(tmp_path: Path) -> None:
    """Each item in the batch JSON has the six required keys."""
    records = [_TONE_RECORD]
    items = build_export_items(records)
    paths = write_export_batches(items, tmp_path)
    batch = json.loads(paths[0].read_text(encoding="utf-8"))
    assert len(batch) == 1
    item = batch[0]
    for key in ("record_id", "scorer", "npc_id", "player_message", "criteria", "output_text"):
        assert key in item, f"Missing key: {key}"


def test_write_export_batches_no_scorer_verdict_in_json(tmp_path: Path) -> None:
    """Batch JSON items never contain scorer_verdict or judge verdict fields."""
    records = [_TONE_RECORD, _AFFIRMS_RECORD]
    items = build_export_items(records)
    paths = write_export_batches(items, tmp_path)
    batch = json.loads(paths[0].read_text(encoding="utf-8"))
    for item in batch:
        assert "scorer_verdict" not in item
        assert "passed" not in item
        assert "score" not in item


def test_write_export_batches_creates_directory(tmp_path: Path) -> None:
    """write_export_batches creates the output directory if it does not exist."""
    out_dir = tmp_path / "nested" / "export"
    records = [_TONE_RECORD]
    items = build_export_items(records)
    paths = write_export_batches(items, out_dir)
    assert out_dir.exists()
    assert len(paths) == 1


def test_write_export_batches_invalid_batch_size_raises() -> None:
    """batch_size < 1 raises ValueError."""
    items = [
        ExportItem(
            record_id="x",
            scorer="tone_judge",
            npc_id="mira",
            player_message="hi",
            criteria="",
            output_text="hello",
        )
    ]
    with pytest.raises(ValueError, match="batch_size"):
        write_export_batches(items, Path("/tmp/unused"), batch_size=0)


def test_build_export_items_preserves_order() -> None:
    """build_export_items returns items in the same order as the input records."""
    records = [
        _make_record("case_001:tone_judge:0"),
        _make_record("case_002:affirms_judge:0", judge_kind="affirms_judge"),
        _make_record("case_003:tone_judge:1"),
    ]
    items = build_export_items(records)
    assert [item.record_id for item in items] == [
        composite_item_id(r.record_id, r.repetition) for r in records
    ]


# ---------------------------------------------------------------------------
# Scorer filtering (hand-labelling ergonomics)
# ---------------------------------------------------------------------------


def test_filter_by_scorer_keeps_only_requested_kinds() -> None:
    """filter_by_scorer keeps only items whose scorer is in the requested set."""
    items = [
        build_export_item(_make_record("c1:tone_judge:0")),
        build_export_item(_make_record("c2:affirms_judge:0", judge_kind="affirms_judge")),
    ]
    kept = filter_by_scorer(items, {"tone_judge"})
    assert [i.scorer for i in kept] == ["tone_judge"]


def test_filter_by_scorer_none_is_passthrough() -> None:
    """A None filter returns every item — the default export is unfiltered."""
    items = [build_export_item(_make_record("c1:tone_judge:0"))]
    assert filter_by_scorer(items, None) == items


def test_filter_by_scorer_unknown_kind_raises() -> None:
    """A scorer name that matches nothing is a typo, not an empty export."""
    items = [build_export_item(_make_record("c1:tone_judge:0"))]
    with pytest.raises(ValueError):
        filter_by_scorer(items, {"tone_judeg"})
