"""
Module: label_import
Layer: evals (eval harness — not part of src/)
Purpose: Validate and import a Claude-CLI labelling session into CalibrationLabel rows.
         Reads minimal JSONL (record_id, scorer, pre_label, notes), joins output_text,
         criteria, player_message, and observed from the transcript index and
         scorer_verdict from the judged index, stamps pre_labeller_model, and writes
         validated CalibrationLabel rows with human_verdict=None. The transcript-index
         builder lives in transcript_index.py and the exception types live in
         label_import_errors.py (both split out to stay under the 300-line cap; the
         transcript-index derivation is also shared with label_export via export_item.py).
Dependencies: argparse, json, pathlib, sys, pydantic, calibration_records, export_item,
              transcript_index, label_import_errors
Used by: python -m evals label-import; make label-import (EVAL-P5.6)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from calibration_records import (
    LABELS_FILE,
    CalibrationLabel,
    read_calibration_labels,
    write_calibration_labels,
)
from export_item import ExportItem
from label_import_errors import (
    ContaminatedRowError,
    MissingVerdictError,
    UnknownRecordIdError,
)
from record_identity import composite_item_id, split_item_id
from transcript_index import build_judged_index, build_transcript_index

# Re-exported for backward compatibility: callers historically imported the
# error types from this module. Do not remove without checking for external
# importers.
__all__ = [
    "ContaminatedRowError",
    "MissingVerdictError",
    "UnknownRecordIdError",
    "RawLabelRow",
    "import_labels",
    "read_raw_rows",
    "main",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CONTAMINATING_FIELDS: frozenset[str] = frozenset({"output_text", "scorer_verdict"})
_DEFAULT_PRE_LABELLER: str = "claude-opus-5"


# ---------------------------------------------------------------------------
# Raw row model
# ---------------------------------------------------------------------------


class RawLabelRow(BaseModel):
    """Minimal JSONL row produced by the Claude-CLI labelling pass.

    The labeller returns only these four fields; all other CalibrationLabel
    fields are joined from the transcript and judged records by import_labels.

    Attributes:
        record_id: Stable identifier matching the generation transcript.
        scorer: Which scorer is being labelled (e.g. 'tone_judge').
        pre_label: The labeller's proposed verdict (True = pass, False = fail).
        notes: Free-text annotation from the labeller (empty string when absent).
    """

    model_config = ConfigDict(frozen=True)

    record_id: str
    scorer: str
    pre_label: bool
    notes: str = ""


# ---------------------------------------------------------------------------
# Core import logic
# ---------------------------------------------------------------------------


def _check_contamination(raw: dict[str, Any], record_id: str) -> None:
    """Raise ContaminatedRowError if any contaminating field is present in the raw dict."""
    for field in _CONTAMINATING_FIELDS:
        if field in raw:
            raise ContaminatedRowError(record_id, field)


def import_labels(
    raw_rows: Sequence[dict[str, Any]],
    transcript_index: Mapping[str, ExportItem],
    judged_index: Mapping[str, bool],
    pre_labeller_model: str,
) -> list[CalibrationLabel]:
    """Join raw label rows with transcript and judged record data into CalibrationLabel rows.

    Args:
        raw_rows: Sequence of raw dicts from the Claude-CLI labelling JSONL.
                  Each must have record_id, scorer, pre_label. May have notes.
                  Must NOT have output_text or scorer_verdict.
        transcript_index: Mapping from item_id to ExportItem, supplying
                         output_text, criteria, player_message, and observed.
                         Built from the generation transcript by
                         transcript_index.build_transcript_index.
        judged_index: Mapping from record_id to scorer_verdict (bool).
                      Built from the judge runner's judged.jsonl or the
                      deterministic_pass result.
        pre_labeller_model: Model identifier that produced pre_label
                            (e.g. 'claude-opus-5').
    Returns:
        List of CalibrationLabel rows with human_verdict=None and adjudicated_at=None.
    Raises:
        ContaminatedRowError: If a raw row carries output_text or scorer_verdict.
        UnknownRecordIdError: If a raw row's record_id is absent from transcript_index.
        ValidationError: If a raw row's fields do not conform to RawLabelRow schema.
    """
    results: list[CalibrationLabel] = []
    for raw in raw_rows:
        record_id: str = raw.get("record_id", "")
        _check_contamination(raw, record_id)

        # Normalise: a bare (pre-composite) record_id means repetition 0.
        base, repetition = split_item_id(record_id)
        item_id = composite_item_id(base, repetition)

        if item_id not in transcript_index:
            raise UnknownRecordIdError(record_id)
        if item_id not in judged_index:
            raise MissingVerdictError(record_id)

        row = RawLabelRow.model_validate(raw)
        export_item = transcript_index[item_id]
        scorer_verdict: bool = judged_index[item_id]

        results.append(
            CalibrationLabel(
                record_id=row.record_id,
                scorer=row.scorer,
                output_text=export_item.output_text,
                scorer_verdict=scorer_verdict,
                pre_label=row.pre_label,
                pre_labeller_model=pre_labeller_model,
                human_verdict=None,
                adjudicated_at=None,
                notes=row.notes,
                criteria=export_item.criteria,
                player_message=export_item.player_message,
                observed=export_item.observed,
            )
        )
    return results


# ---------------------------------------------------------------------------
# JSONL persistence helpers
# ---------------------------------------------------------------------------


def read_raw_rows(path: Path) -> list[dict[str, Any]]:
    """Load raw label rows from a JSONL file written by the Claude-CLI labelling pass.

    Args:
        path: Path to the labeller's minimal JSONL output.
    Returns:
        List of raw dicts in file order.
    Raises:
        FileNotFoundError: If the path does not exist.
        json.JSONDecodeError: If any line is not valid JSON.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the label-import verb."""
    p = argparse.ArgumentParser(
        prog="python -m evals label-import",
        description=(
            "Import a Claude-CLI labelling session into CalibrationLabel rows. "
            "Reads raw JSONL (record_id, scorer, pre_label, notes), joins output_text "
            "from the transcript and scorer_verdict from judged records, "
            "then appends validated rows to the labels file."
        ),
    )
    p.add_argument(
        "--raw",
        type=Path,
        required=True,
        metavar="PATH",
        help="Path to the labeller's minimal JSONL output.",
    )
    p.add_argument(
        "--transcript",
        type=Path,
        required=True,
        metavar="PATH",
        help="Path to the generation transcript's outputs.jsonl.",
    )
    p.add_argument(
        "--judged",
        type=Path,
        required=True,
        nargs="+",
        metavar="PATH",
        help=(
            "Path(s) to judged JSONL files. Pass both the LLM judge's judged.jsonl "
            "and the deterministic-verdicts output to cover every scorer."
        ),
    )
    p.add_argument(
        "--out",
        type=Path,
        default=LABELS_FILE,
        metavar="PATH",
        help=f"Destination labels JSONL file (default: {LABELS_FILE}).",
    )
    p.add_argument(
        "--model",
        default=_DEFAULT_PRE_LABELLER,
        metavar="MODEL",
        help=f"Pre-labeller model identifier (default: {_DEFAULT_PRE_LABELLER}).",
    )
    p.add_argument(
        "--append",
        action="store_true",
        help="Append to an existing labels file rather than overwriting it.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the label-import verb.

    Args:
        argv: Argument list; defaults to sys.argv[1:].
    Returns:
        0 on success, 1 on error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    raw_rows = read_raw_rows(args.raw)
    transcript_index = build_transcript_index(args.transcript)

    judged_index: dict[str, bool] = {}
    for judged_path in args.judged:
        judged_index.update(build_judged_index(judged_path))

    new_labels = import_labels(raw_rows, transcript_index, judged_index, args.model)

    existing: list[CalibrationLabel] = []
    if args.append and args.out.exists():
        existing = read_calibration_labels(args.out)

    write_calibration_labels(args.out, existing + new_labels)
    print(f"Imported {len(new_labels)} label(s) → {args.out}", file=sys.stderr)
    return 0
