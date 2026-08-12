"""
Module: eval_records
Layer: evals (eval harness — not part of src/)
Purpose: Pydantic v2 record models for the two-phase generate→judge eval pipeline.
         GenerationRecord holds one engine reply + judge metadata; JudgedRecord
         adds the verdict; TranscriptFile bundles records for persist/replay.
Dependencies: pydantic, stdlib (json, logging, pathlib, datetime, typing), run_config, retrieved_item
Used by: generate_runner, judge_runner, deterministic_records, e2e/scenarios/conftest
         (persist_scenario_records)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

from retrieved_item import RetrievedItem
from run_config import RunConfig


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TRANSCRIPT_VERSION: int = 2
_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TranscriptVersionError(ValueError):
    """Raised when a transcript file has an unsupported schema version.

    Attributes:
        found: The version number found in the file.
        expected: The version number this reader requires.
    """

    def __init__(self, *, found: int, expected: int) -> None:
        self.found = found
        self.expected = expected
        super().__init__(
            f"Transcript version mismatch: found {found}, expected {expected}. "
            f"This reader requires version {expected}; v{found} transcripts are not supported."
        )


# ---------------------------------------------------------------------------
# Deterministic matcher kinds (EVAL-P6.1)
# ---------------------------------------------------------------------------

# Every non-judge matcher kind evaluable off a transcript, plus the grounded
# anti-hallucination check (not a matchers.py kind, but scored the same way —
# no LLM call, replayed from stored metadata). Single source of truth: both
# GenerationRecord.matcher_kind and deterministic_records.covered_matcher_kinds()
# derive from this alias so the two can never drift apart silently.
DeterministicMatcherKind = Literal[
    "schema",
    "min_length",
    "keyword_any",
    "keyword_all",
    "keyword_none",
    "in_set",
    "range",
    "substring",
    "regex",
    "context_block_expected",
    "anti_hallucination_grounded",
]


# ---------------------------------------------------------------------------
# Record models
# ---------------------------------------------------------------------------


class GenerationRecord(BaseModel):
    """One engine reply plus the metadata needed to judge it later.

    Frozen so records are immutable once created — safe to cache and serialize.

    Attributes:
        record_id: Stable ID of the form ``<case_id>:<judge_kind>:<index>``.
        source: Which runner produced this record.
        npc_id: Character that produced the npc_response.
        player_id: Player interacting with the NPC.
        player_message: The player's dialogue turn.
        npc_response: The engine reply to evaluate.
        criteria: Verbatim criteria string for _run_binary_judge.
        judge_kind: Which judge function to apply, or None for deterministic checks.
        matcher_kind: Which deterministic matcher applies when judge_kind is None
            (e.g. 'min_length', 'schema'). None for judge-based records and for
            records written before EVAL-P6.1.
        expected_polarity: How to map the YES/NO judge verdict to pass/fail.
        active_conditions: Active world conditions at the time of generation.
        metadata: Arbitrary extra data. Deterministic records (matcher_kind set)
            store {"expectation": <raw expectation dict>, "response": <raw API
            response dict>} here so deterministic_records.score_record can replay
            the matcher without re-calling the engine; anti_hallucination_grounded
            records store {"expected_fact_substrings": [...], "response": {...}}.
        repetition: Zero-based repeat index within a k-repeat run (default 0).
        duration_ms: Wall-clock milliseconds taken to generate npc_response (default 0).
        retrieved_context: Context items captured from GET /v1/admin/debug/retrieval at
            generation time. An approximation — see RetrievedItem module docstring.
    """

    model_config = ConfigDict(frozen=True)

    record_id: str
    source: Literal["runner", "anti_hallucination", "scenario"]
    npc_id: str
    player_id: str
    player_message: str
    npc_response: str
    criteria: str
    judge_kind: Literal["tone_judge", "affirms_judge", "refusal_judge"] | None
    matcher_kind: DeterministicMatcherKind | None = None
    expected_polarity: Literal["pass_on_yes", "pass_on_no"]
    active_conditions: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
    repetition: int = 0
    duration_ms: int = 0
    retrieved_context: tuple[RetrievedItem, ...] = ()


class JudgedRecord(GenerationRecord):
    """A GenerationRecord augmented with the judge's verdict.

    Attributes:
        passed: Whether the record met its expectation after polarity is applied.
        score: Raw YES/NO verdict from the judge (None = infra failure/inconclusive).
        reasoning: Judge's reasoning text (empty string when score is True).
    """

    passed: bool
    score: bool | None
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Transcript file model
# ---------------------------------------------------------------------------


class TranscriptFile(BaseModel):
    """A bundle of GenerationRecords written during a generate pass.

    Attributes:
        version: Schema version (2 as of EVAL-P1.3; read_transcript rejects v1 loudly).
        generated_at: ISO-8601 timestamp of when the transcript was written.
        gen_id: Identifier for this generation run (e.g. 'smoke-001'). Empty when
            the transcript was written by a pre-EVAL-P1.4 runner.
        k: Number of repetitions per case in this run. Defaults to 1.
        config: Exact reproducibility snapshot for this run. None when the transcript
            was written by a pre-EVAL-P1.4 runner.
        records: Ordered tuple of GenerationRecords from a single run.
    """

    model_config = ConfigDict(frozen=True)

    version: int = _TRANSCRIPT_VERSION
    generated_at: str
    gen_id: str = ""
    k: int = 1
    config: RunConfig | None = None
    records: tuple[GenerationRecord, ...]


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def write_generation_dir(
    gen_dir: Path,
    records: Sequence[GenerationRecord],
    *,
    gen_id: str,
    k: int,
    config: RunConfig | None = None,
) -> None:
    """Write a k-repeat generation run to <gen_dir>/{meta.json,outputs.jsonl}.

    meta.json holds the TranscriptFile metadata block (no records array).
    outputs.jsonl has one GenerationRecord as compact JSON per line.
    Creates gen_dir and parents if needed; overwrites any existing files.

    Args:
        gen_dir: Target directory (e.g. evals/generations/smoke/).
        records: Ordered sequence of GenerationRecords to persist.
        gen_id: Generation run identifier written into meta.json.
        k: Number of repetitions per case in this run.
        config: Reproducibility snapshot; None for pre-EVAL-P1.4 callers.
    """
    gen_dir.mkdir(parents=True, exist_ok=True)
    meta = TranscriptFile(
        generated_at=datetime.now(timezone.utc).isoformat(),
        gen_id=gen_id,
        k=k,
        config=config,
        records=(),
    )
    (gen_dir / "meta.json").write_text(
        meta.model_dump_json(indent=2, exclude={"records"}),
        encoding="utf-8",
    )
    jsonl_lines = "\n".join(r.model_dump_json() for r in records)
    (gen_dir / "outputs.jsonl").write_text(jsonl_lines, encoding="utf-8")


def write_transcript(path: Path, records: Sequence[GenerationRecord]) -> None:
    """Serialise records to a JSON transcript file.

    Creates parent directories if needed. Overwrites any existing file.
    Writes schema version 2; the gen_id, k, and config fields default to empty
    sentinel values until generate_runner is updated in EVAL-P1.4.

    Args:
        path: Destination file path (typically under e2e/transcripts/).
        records: Ordered sequence of GenerationRecords to persist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tf = TranscriptFile(
        generated_at=datetime.now(timezone.utc).isoformat(),
        records=tuple(records),
    )
    path.write_text(tf.model_dump_json(indent=2), encoding="utf-8")


def read_transcript(path: Path) -> TranscriptFile:
    """Load and validate a transcript file.

    Supports both formats written by this module: the legacy single-file
    TranscriptFile JSON (write_transcript) and the gen-dir split format
    (write_generation_dir, meta.json + outputs.jsonl). The split format is
    detected by filename (``outputs.jsonl``) plus a sibling ``meta.json``.

    Args:
        path: Path to a JSON transcript file, or to a gen-dir's outputs.jsonl.
    Returns:
        Validated TranscriptFile (version 2 only).
    Raises:
        TranscriptVersionError: If the file's version field is not 2.
        ValidationError: If the file does not conform to the TranscriptFile schema.
        FileNotFoundError: If the path does not exist.
    """
    meta_path = path.with_name("meta.json")
    if path.name == "outputs.jsonl" and meta_path.exists():
        return _read_generation_dir(path, meta_path)

    raw = path.read_text(encoding="utf-8")
    try:
        header = json.loads(raw)
        found_version = header.get("version")
    except json.JSONDecodeError as exc:
        _logger.warning("transcript at %s: JSON parse failed, treating as version-mismatch: %s", path, exc)
        found_version = None
    if found_version != _TRANSCRIPT_VERSION:
        raise TranscriptVersionError(
            found=int(found_version) if isinstance(found_version, int) else 0,
            expected=_TRANSCRIPT_VERSION,
        )
    return TranscriptFile.model_validate_json(raw)


def _read_generation_dir(outputs_path: Path, meta_path: Path) -> TranscriptFile:
    """Reassemble a TranscriptFile from the gen-dir split format.

    Args:
        outputs_path: Path to outputs.jsonl (one GenerationRecord per line).
        meta_path: Path to the sibling meta.json (TranscriptFile minus records).
    Returns:
        Validated TranscriptFile combining meta.json fields with the parsed records.
    Raises:
        TranscriptVersionError: If meta.json's version field is not 2.
        ValidationError: If either file does not conform to its schema.
    """
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    found_version = meta.get("version")
    if found_version != _TRANSCRIPT_VERSION:
        raise TranscriptVersionError(
            found=int(found_version) if isinstance(found_version, int) else 0,
            expected=_TRANSCRIPT_VERSION,
        )
    lines = [line for line in outputs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    meta["records"] = [json.loads(line) for line in lines]
    return TranscriptFile.model_validate(meta)
