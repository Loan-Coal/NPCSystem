"""
Module: transcript_index
Layer: evals (eval harness — not part of src/)
Purpose: Build item_id-keyed indexes from a generation transcript and a judged
         verdicts file, for label_import's join step. Reuses export_item's
         GenerationRecord → ExportItem derivation so the labelling artifact and
         the adjudication display share one source of criteria/observed/
         player_message/output_text, rather than parsing outputs.jsonl by hand
         a second time and re-deriving criteria rendering separately.
Dependencies: json, pathlib, eval_records, export_item, record_identity
Used by: label_import (EVAL-P5.6 join step; makes human adjudication decidable)
"""

from __future__ import annotations

import json
from pathlib import Path

from eval_records import read_transcript
from export_item import ExportItem, build_export_item
from record_identity import composite_item_id

# ---------------------------------------------------------------------------
# Index builders
# ---------------------------------------------------------------------------


def build_transcript_index(transcript_path: Path) -> dict[str, ExportItem]:
    """Build an item_id→ExportItem index from a generation transcript.

    Keyed by the repetition-qualified item id, not the bare record_id: a
    k-repeat run emits k records sharing one record_id with different
    npc_response text, so a bare-record_id dict would keep only the last
    repetition and silently join labels to the wrong output (see
    record_identity module docstring).

    Each ExportItem carries output_text, criteria, player_message, and
    observed — everything label_import needs to join onto a raw label row
    without re-deriving criteria rendering itself.

    Args:
        transcript_path: Path to the outputs.jsonl of a generation run (or any
            path read_transcript accepts).
    Returns:
        Dict mapping composite item_id to its ExportItem.
    Raises:
        FileNotFoundError: If the path does not exist.
        UnknownMatcherKindError: If a deterministic record's matcher kind has
            no criteria rendering rule.
    """
    transcript = read_transcript(transcript_path)
    return {
        composite_item_id(record.record_id, record.repetition): build_export_item(record)
        for record in transcript.records
    }


def read_transcript_provenance(transcript_path: Path) -> tuple[str, str]:
    """Return (gen_id, golden_set_version) for a generation transcript.

    Stamped onto every imported CalibrationLabel so a label can never be
    silently attributed to a run other than the one it was made against.

    Args:
        transcript_path: Path to the outputs.jsonl of a generation run.
    Returns:
        (gen_id, golden_set_version). Either is "" for pre-EVAL-P1.4
        transcripts that never recorded it.
    """
    transcript = read_transcript(transcript_path)
    golden = transcript.config.golden_set_version if transcript.config else ""
    return transcript.gen_id, golden


def build_judged_index(judged_path: Path) -> dict[str, bool]:
    """Build an item_id→scorer_verdict index from a judged.jsonl file.

    Keyed by the repetition-qualified item id for the same reason as
    build_transcript_index — see that function's docstring.

    Args:
        judged_path: Path to the judged.jsonl of a judge/deterministic pass.
    Returns:
        Dict mapping composite item_id to the passed (scorer_verdict) bool.
    Raises:
        FileNotFoundError: If the path does not exist.
    """
    index: dict[str, bool] = {}
    for line in judged_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        key = composite_item_id(obj["record_id"], int(obj.get("repetition", 0)))
        index[key] = bool(obj.get("passed", False))
    return index
