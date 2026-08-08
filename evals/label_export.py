"""
Module: label_export
Layer: evals (eval harness — not part of src/)
Purpose: Export transcript records as batches of at most 25 items for the CLI
         labelling pass (EVAL-P5.6, replacing EVAL-P5.2's httpx runner).
         Each item carries record_id, scorer, npc_id, player_message, criteria,
         output_text, and — for graph scorer records — a vocabulary snapshot.
         scorer_verdict and all judge verdicts are NEVER emitted: the artifact
         is void if the labeller can see the answer being measured.
Dependencies: argparse, json, pathlib, sys, pydantic, eval_records
Used by: python -m evals label-export; make label-export (EVAL-P5.6)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict

from eval_records import GenerationRecord, read_transcript

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_BATCH_SIZE: int = 25

# Scorer kinds whose export items include a vocabulary block so labellers can
# verify entity/event IDs mentioned in output_text against the graph.
GRAPH_SCORER_KINDS: frozenset[str] = frozenset({"entity_scorer", "knowledge_scorer"})


# ---------------------------------------------------------------------------
# Export item model
# ---------------------------------------------------------------------------


class ExportItem(BaseModel):
    """One item in an export batch, ready for the LABEL_PROMPT.md labelling pass.

    Fields deliberately exclude scorer_verdict, judge verdicts, and metadata
    that would reveal the answer the labeller is measuring.

    Attributes:
        record_id: Stable identifier from the generation transcript.
        scorer: Which scorer is being calibrated (e.g. 'tone_judge').
        npc_id: Character that produced the output.
        player_message: The player's dialogue turn that prompted the response.
        criteria: The judge criteria string (or '' for deterministic scorers).
        output_text: The NPC response text to be labelled.
        vocabulary: Graph node-ID snapshot for graph scorer records;
                    None for all other scorer kinds.
    """

    model_config = ConfigDict(frozen=True)

    record_id: str
    scorer: str
    npc_id: str
    player_message: str
    criteria: str
    output_text: str
    vocabulary: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------


def _scorer_for_record(record: GenerationRecord) -> str:
    """Derive the calibration scorer name from a GenerationRecord.

    Args:
        record: A GenerationRecord from the generation transcript.
    Returns:
        The judge_kind string if the record is LLM-judged, otherwise
        the matcher_kind string, otherwise 'unknown'.
    """
    if record.judge_kind is not None:
        return record.judge_kind
    if record.matcher_kind is not None:
        return record.matcher_kind
    return "unknown"


def build_export_item(
    record: GenerationRecord,
    vocabulary: dict[str, Any] | None = None,
) -> ExportItem:
    """Build one ExportItem from a GenerationRecord.

    scorer_verdict and judge verdicts are never included.

    Args:
        record: Source GenerationRecord.
        vocabulary: Graph vocabulary dict to include for graph scorer records;
                    ignored (left None) for non-graph scorer records.
    Returns:
        An ExportItem suitable for JSON serialisation.
    """
    scorer = _scorer_for_record(record)
    return ExportItem(
        record_id=record.record_id,
        scorer=scorer,
        npc_id=record.npc_id,
        player_message=record.player_message,
        criteria=record.criteria,
        output_text=record.npc_response,
        vocabulary=vocabulary if scorer in GRAPH_SCORER_KINDS else None,
    )


def build_export_items(
    records: Sequence[GenerationRecord],
    vocabulary: dict[str, Any] | None = None,
) -> list[ExportItem]:
    """Build export items from a sequence of GenerationRecords.

    Args:
        records: GenerationRecords from the generation transcript.
        vocabulary: Graph vocabulary dict; included only for graph scorer records.
    Returns:
        List of ExportItems in the same order as records.
    """
    return [build_export_item(record, vocabulary) for record in records]


def write_export_batches(
    items: Sequence[ExportItem],
    out_dir: Path,
    batch_size: int = MAX_BATCH_SIZE,
) -> list[Path]:
    """Write items as JSON batch files of at most batch_size items each.

    Files are named batch_001.json, batch_002.json, …
    Creates out_dir and parents if needed; overwrites any existing batch files.

    Args:
        items: ExportItems to write.
        out_dir: Directory to write batch files into.
        batch_size: Maximum number of items per batch file (default 25).
    Returns:
        Ordered list of Path objects for the written batch files.
    Raises:
        ValueError: If batch_size is less than 1.
    """
    if batch_size < 1:
        raise ValueError(f"batch_size must be at least 1, got {batch_size}")

    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    items_list = list(items)

    for batch_num, start in enumerate(range(0, max(len(items_list), 1), batch_size), 1):
        batch = items_list[start : start + batch_size]
        if not batch:
            break
        path = out_dir / f"batch_{batch_num:03d}.json"
        payload = [item.model_dump() for item in batch]
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        paths.append(path)

    return paths


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the label-export verb."""
    p = argparse.ArgumentParser(
        prog="python -m evals label-export",
        description=(
            "Export transcript records as batches for the Claude-CLI labelling pass. "
            "Each batch file contains at most 25 items as JSON. "
            "scorer_verdict and judge verdicts are NEVER included."
        ),
    )
    p.add_argument(
        "--transcript",
        type=Path,
        required=True,
        metavar="PATH",
        help="Path to the generation transcript JSON (TranscriptFile format).",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        metavar="DIR",
        help="Directory to write batch_001.json … batch_NNN.json files into.",
    )
    p.add_argument(
        "--vocabulary",
        type=Path,
        default=None,
        metavar="PATH",
        help="Optional path to a vocabulary.json snapshot for graph scorer records.",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=MAX_BATCH_SIZE,
        metavar="N",
        help=f"Items per batch file (default: {MAX_BATCH_SIZE}).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the label-export verb.

    Args:
        argv: Argument list; defaults to sys.argv[1:].
    Returns:
        0 on success, 1 on error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    transcript = read_transcript(args.transcript)
    records = list(transcript.records)

    vocab_dict: dict[str, Any] | None = None
    if args.vocabulary is not None and args.vocabulary.exists():
        vocab_dict = json.loads(args.vocabulary.read_text(encoding="utf-8"))

    items = build_export_items(records, vocab_dict)
    paths = write_export_batches(items, args.out_dir, args.batch_size)

    print(
        f"Exported {len(items)} item(s) across {len(paths)} batch file(s) → {args.out_dir}",
        file=sys.stderr,
    )
    return 0
