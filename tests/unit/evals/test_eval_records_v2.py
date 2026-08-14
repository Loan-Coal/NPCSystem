"""
Module: test_eval_records_v2
Layer: test (unit)
Purpose: Unit tests for eval_records.py schema v2 — TranscriptVersionError on v1,
         v2 round-trip correctness, and new field presence on TranscriptFile /
         GenerationRecord.
Dependencies: json, pathlib, pytest, eval_records, run_config, retrieved_item (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval_records import (
    LEGACY_HARNESS_VERSION,
    GenerationRecord,
    TranscriptFile,
    TranscriptVersionError,
    read_transcript,
    write_generation_dir,
)
from retrieved_item import RetrievedItem
from run_config import RunConfig

_MINIMAL_RUN_CONFIG = RunConfig(
    prompt_version="test_v1",
    generation_model="test-model:7b",
    temperature=0.5,
    top_p=0.9,
    max_tokens=256,
    judge_model="judge-model:7b",
    retrieval_profile="default",
    git_sha="abc1234",
    golden_set_version="v1",
    harness_version="test_harness_v1",
)

_BASE_FIELDS: dict = {
    "record_id": "case_001:tone_judge:0",
    "source": "runner",
    "npc_id": "mira_innkeeper",
    "player_id": "player_1",
    "player_message": "Hello",
    "npc_response": "Welcome!",
    "criteria": "tone is warm",
    "judge_kind": "tone_judge",
    "expected_polarity": "pass_on_yes",
    "repetition": 0,
    "duration_ms": 123,
    "retrieved_context": (
        RetrievedItem(key="npc_identity", tier="unknown", priority=0, text="Mira runs the inn."),
    ),
}


def test_read_transcript_rejects_v1(tmp_path: Path) -> None:
    """read_transcript raises TranscriptVersionError for version=1 transcripts."""
    v1_json = json.dumps({
        "version": 1,
        "generated_at": "2026-01-01T00:00:00+00:00",
        "records": [],
    })
    p = tmp_path / "v1.json"
    p.write_text(v1_json, encoding="utf-8")

    with pytest.raises(TranscriptVersionError) as exc_info:
        read_transcript(p)

    msg = str(exc_info.value)
    assert "1" in msg
    assert "2" in msg


def test_v2_roundtrip(tmp_path: Path) -> None:
    """A v2 transcript survives a JSON write→read round-trip unchanged."""
    record = GenerationRecord(**_BASE_FIELDS)
    tf = TranscriptFile(
        gen_id="smoke-001",
        k=1,
        config=_MINIMAL_RUN_CONFIG,
        generated_at="2026-08-06T00:00:00+00:00",
        records=(record,),
    )
    p = tmp_path / "transcript.json"
    p.write_text(tf.model_dump_json(indent=2), encoding="utf-8")

    loaded = read_transcript(p)

    assert loaded.version == 2
    assert loaded.gen_id == "smoke-001"
    assert loaded.k == 1
    assert loaded.config is not None
    assert loaded.config.generation_model == "test-model:7b"
    assert len(loaded.records) == 1
    r = loaded.records[0]
    assert r.repetition == 0
    assert r.duration_ms == 123
    assert len(r.retrieved_context) == 1
    assert r.retrieved_context[0].key == "npc_identity"
    assert r.retrieved_context[0].text == "Mira runs the inn."


def test_run_config_seed_field_defaults_to_none() -> None:
    """RunConfig carries a real seed (DEC-176), defaulting to None so pre-seed artifacts still load."""
    assert "seed" in RunConfig.model_fields
    assert RunConfig.model_fields["seed"].default is None


def test_retrieved_item_is_frozen() -> None:
    """RetrievedItem must be immutable (frozen=True)."""
    item = RetrievedItem(key="k", tier="unknown", priority=0, text="t")
    with pytest.raises(Exception):
        item.key = "new_key"  # type: ignore[misc]


def test_read_transcript_reads_gen_dir_split_format(tmp_path: Path) -> None:
    """read_transcript reconstructs a TranscriptFile from meta.json + outputs.jsonl.

    Regression test: write_generation_dir (used by generate_runner's gen-id path)
    splits a run into meta.json (header) and outputs.jsonl (one record per line),
    which is not a single JSON document with a top-level "version" key. Before this
    fix, read_transcript tried json.loads() on the whole outputs.jsonl, failed to
    parse multi-line JSONL as one JSON value, and raised TranscriptVersionError
    (found=0) even though the run was version 2 — breaking judge/score/label-export
    for every gen-id run.
    """
    record = GenerationRecord(**_BASE_FIELDS)
    gen_dir = tmp_path / "k3_deadbeef"
    write_generation_dir(gen_dir, [record, record], gen_id="k3_deadbeef", k=3, config=_MINIMAL_RUN_CONFIG)

    loaded = read_transcript(gen_dir / "outputs.jsonl")

    assert loaded.version == 2
    assert loaded.gen_id == "k3_deadbeef"
    assert loaded.k == 3
    assert loaded.config is not None
    assert loaded.config.generation_model == "test-model:7b"
    assert len(loaded.records) == 2
    assert loaded.records[0].record_id == "case_001:tone_judge:0"


def test_read_transcript_rejects_gen_dir_v1(tmp_path: Path) -> None:
    """read_transcript raises TranscriptVersionError for a gen-dir meta.json with the wrong version."""
    gen_dir = tmp_path / "stale_run"
    gen_dir.mkdir()
    (gen_dir / "meta.json").write_text(
        json.dumps({"version": 1, "generated_at": "2026-01-01T00:00:00+00:00", "gen_id": "stale", "k": 1, "config": None}),
        encoding="utf-8",
    )
    (gen_dir / "outputs.jsonl").write_text("", encoding="utf-8")

    with pytest.raises(TranscriptVersionError):
        read_transcript(gen_dir / "outputs.jsonl")


def test_transcript_version_error_names_both_versions() -> None:
    """TranscriptVersionError message includes both found and expected version numbers."""
    err = TranscriptVersionError(found=1, expected=2)
    msg = str(err)
    assert "1" in msg
    assert "2" in msg


def test_read_transcript_reads_gen_dir_predating_harness_version(tmp_path: Path) -> None:
    """read_transcript loads a gen-dir meta.json written before EVAL-P18.1.

    Regression test: EVAL-P18.1 (2026-08-12) made RunConfig.harness_version a
    required field with no default. The committed baseline artifact
    evals/generations/k3_73e6c36/ was generated 2026-08-08, before that field
    existed — its meta.json's config dict has every RunConfig field except
    harness_version. Before this fix, read_transcript raised
    pydantic.ValidationError("harness_version Field required") on that gen-dir,
    breaking `evals judge` and `label_import.read_transcript_provenance` for the
    one artifact EVAL-P19.4 is specced to re-judge. RunConfig itself keeps no
    default (ISSUE-152's rationale: a silent default would let two incomparable
    runs compare cleanly by accident) — only the legacy-read boundary tolerates
    the gap, and it does so visibly via the LEGACY_HARNESS_VERSION sentinel
    rather than inventing a real-looking hash.
    """
    gen_dir = tmp_path / "pre_p18_1_run"
    gen_dir.mkdir()
    legacy_config = _MINIMAL_RUN_CONFIG.model_dump()
    del legacy_config["harness_version"]
    meta = {
        "version": 2,
        "generated_at": "2026-08-08T11:18:15+00:00",
        "gen_id": "k3_73e6c36",
        "k": 3,
        "config": legacy_config,
    }
    (gen_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    record = GenerationRecord(**_BASE_FIELDS)
    (gen_dir / "outputs.jsonl").write_text(record.model_dump_json() + "\n", encoding="utf-8")

    loaded = read_transcript(gen_dir / "outputs.jsonl")

    assert loaded.config is not None
    assert loaded.config.harness_version == LEGACY_HARNESS_VERSION
    assert loaded.gen_id == "k3_73e6c36"
