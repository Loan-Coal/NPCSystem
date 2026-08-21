"""
Module: eval_records
Layer: evals (eval harness — not part of src/)
Purpose: Persistence for the two-phase generate→judge eval pipeline — write and
         read v2 transcripts and generation directories. The record models
         themselves live in transcript_models and are re-exported here, so this
         module remains the single import site every caller already uses.
Dependencies: pydantic, stdlib (json, pathlib, datetime, typing), run_config,
         transcript_models
Used by: generate_runner, judge_runner, deterministic_records, e2e/scenarios/conftest
         (persist_scenario_records)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from run_config import RunConfig
from transcript_models import (
    LEGACY_HARNESS_VERSION,
    DeterministicMatcherKind,
    GenerationRecord,
    JudgedRecord,
    TranscriptFile,
    TranscriptVersionError,
    _logger,
    _TRANSCRIPT_VERSION,
)

# Re-exported so `from eval_records import GenerationRecord` (and every other
# model name) keeps working unchanged after the transcript_models split.
__all__ = [
    "LEGACY_HARNESS_VERSION",
    "DeterministicMatcherKind",
    "GenerationRecord",
    "JudgedRecord",
    "TranscriptFile",
    "TranscriptVersionError",
    "read_transcript",
    "write_generation_dir",
    "write_transcript",
]


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
    config = meta.get("config")
    if isinstance(config, dict) and "harness_version" not in config:
        _logger.warning(
            "gen-dir %s predates EVAL-P18.1's harness_version field; "
            "stamping %s (not comparable to any real run)",
            meta_path.parent,
            LEGACY_HARNESS_VERSION,
        )
        meta["config"] = {**config, "harness_version": LEGACY_HARNESS_VERSION}
    lines = [line for line in outputs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    meta["records"] = [json.loads(line) for line in lines]
    return TranscriptFile.model_validate(meta)
