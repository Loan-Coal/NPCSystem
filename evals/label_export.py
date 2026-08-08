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

from criteria_rendering import observed_fields, render_criteria
from eval_records import GenerationRecord, read_transcript
from record_identity import composite_item_id

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_BATCH_SIZE: int = 25

# Grounded AH records store their parameters directly rather than under
# metadata["expectation"] (see deterministic_records.build_ah_grounded_record).
_GROUNDED_KIND: str = "anti_hallucination_grounded"
_GROUNDED_PARAM_KEY: str = "expected_fact_substrings"

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
        record_id: Repetition-qualified identifier ('<case>:<kind>:<index>#r<n>').
                   Unique per labelled output, unlike the transcript's bare
                   record_id which repeats k times in a k-repeat run.
        scorer: Which scorer is being calibrated (e.g. 'tone_judge').
        npc_id: Character that produced the output.
        player_message: The player's dialogue turn that prompted the response.
        criteria: What the scorer requires. Verbatim judge criteria for LLM-judge
                  records; rendered from the matcher's expectation dict for
                  deterministic records (never empty — see criteria_rendering).
        output_text: The NPC response text to be labelled.
        observed: Response fields the matcher inspects beyond output_text
                  (facial_expression.type, relation_deltas.trust, …). Empty for
                  text-only scorers; those are fully judgeable from output_text.
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
    observed: dict[str, Any] = {}
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


def _expectation_for(record: GenerationRecord) -> dict[str, Any]:
    """Recover a deterministic record's matcher parameters from its metadata.

    Grounded AH records store expected_fact_substrings at the top level of
    metadata; every other deterministic kind nests its raw expectation dict
    under metadata["expectation"].
    """
    if record.matcher_kind == _GROUNDED_KIND:
        return {_GROUNDED_PARAM_KEY: record.metadata.get(_GROUNDED_PARAM_KEY, [])}
    return record.metadata.get("expectation", {}) or {}


def build_export_item(
    record: GenerationRecord,
    vocabulary: dict[str, Any] | None = None,
) -> ExportItem:
    """Build one ExportItem from a GenerationRecord.

    LLM-judge records carry their criteria verbatim. Deterministic records carry
    criteria="" on the record itself (the field is reserved for judge prompts),
    so their criteria is rendered from metadata["expectation"] and the response
    fields the matcher inspects are surfaced in `observed` — without both, the
    item is unlabelable.

    scorer_verdict and judge verdicts are never included.

    Args:
        record: Source GenerationRecord.
        vocabulary: Graph vocabulary dict to include for graph scorer records;
                    ignored (left None) for non-graph scorer records.
    Returns:
        An ExportItem suitable for JSON serialisation.
    Raises:
        UnknownMatcherKindError: If a deterministic record's matcher kind has no
            rendering rule — a silent blank criteria would make it unlabelable.
    """
    scorer = _scorer_for_record(record)
    criteria = record.criteria
    observed: dict[str, Any] = {}

    if record.judge_kind is None and record.matcher_kind is not None:
        expectation = _expectation_for(record)
        response = record.metadata.get("response", {}) or {}
        criteria = render_criteria(scorer, expectation)
        observed = observed_fields(scorer, expectation, response)

    return ExportItem(
        record_id=composite_item_id(record.record_id, record.repetition),
        scorer=scorer,
        npc_id=record.npc_id,
        player_message=record.player_message,
        criteria=criteria,
        output_text=record.npc_response,
        observed=observed,
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


def filter_by_scorer(
    items: Sequence[ExportItem],
    scorers: set[str] | None,
) -> list[ExportItem]:
    """Keep only items whose scorer is in `scorers`.

    Used to export a labelling set for the scorers worth a human's time. Scorers
    whose verdict never varies across a run (e.g. schema, which passed every
    record) cannot yield a meaningful kappa no matter how carefully they are
    labelled, so excluding them is a real saving rather than a shortcut.

    Args:
        items: Export items to filter.
        scorers: Scorer names to keep; None means keep everything.
    Returns:
        Items in original order, filtered.
    Raises:
        ValueError: If a requested scorer matches no item — a silent empty
            export would look like a completed pass with nothing to label.
    """
    if scorers is None:
        return list(items)

    present = {item.scorer for item in items}
    unknown = scorers - present
    if unknown:
        raise ValueError(
            f"No items for scorer(s) {sorted(unknown)}. Present in this transcript: "
            f"{sorted(present)}"
        )
    return [item for item in items if item.scorer in scorers]


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
    p.add_argument(
        "--scorer",
        action="append",
        default=None,
        metavar="NAME",
        help=(
            "Export only this scorer; repeatable. Omit to export every scorer. "
            "Use to skip scorers whose verdict never varies (no kappa signal)."
        ),
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
    items = filter_by_scorer(items, set(args.scorer) if args.scorer else None)
    paths = write_export_batches(items, args.out_dir, args.batch_size)

    scope = f" for {sorted(set(args.scorer))}" if args.scorer else ""
    print(
        f"Exported {len(items)} item(s){scope} across {len(paths)} batch file(s) → {args.out_dir}",
        file=sys.stderr,
    )
    return 0
