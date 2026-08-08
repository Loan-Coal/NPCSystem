"""
Module: label_import
Layer: evals (eval harness — not part of src/)
Purpose: Validate and import a Claude-CLI labelling session into CalibrationLabel rows.
         Reads minimal JSONL (record_id, scorer, pre_label, notes), joins output_text
         from the transcript index and scorer_verdict from the judged index, stamps
         pre_labeller_model, and writes validated CalibrationLabel rows with
         human_verdict=None.
Dependencies: argparse, json, pathlib, sys, pydantic, calibration_records
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CONTAMINATING_FIELDS: frozenset[str] = frozenset({"output_text", "scorer_verdict"})
_DEFAULT_PRE_LABELLER: str = "claude-opus-5"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class UnknownRecordIdError(Exception):
    """Raised when a raw label row references a record_id absent from the transcript index.

    Attributes:
        record_id: The offending identifier.
    """

    def __init__(self, record_id: str) -> None:
        self.record_id = record_id
        super().__init__(
            f"record_id {record_id!r} not found in transcript index — "
            f"this row cannot be imported without its source output_text and scorer_verdict."
        )


class ContaminatedRowError(Exception):
    """Raised when a raw label row carries a field that would contaminate labelling.

    A row containing output_text or scorer_verdict has been exposed to the
    answer it is measured against; the artifact is void if used.

    Attributes:
        record_id: The offending row's identifier.
        field: The contaminating field name.
    """

    def __init__(self, record_id: str, field: str) -> None:
        self.record_id = record_id
        self.field = field
        super().__init__(
            f"Raw label row {record_id!r} contains contaminating field {field!r} — "
            f"the labeller must not see scorer_verdict or output_text before labelling."
        )


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
    transcript_index: Mapping[str, str],
    judged_index: Mapping[str, bool],
    pre_labeller_model: str,
) -> list[CalibrationLabel]:
    """Join raw label rows with transcript and judged record data into CalibrationLabel rows.

    Args:
        raw_rows: Sequence of raw dicts from the Claude-CLI labelling JSONL.
                  Each must have record_id, scorer, pre_label. May have notes.
                  Must NOT have output_text or scorer_verdict.
        transcript_index: Mapping from record_id to output_text (npc_response).
                         Built from the generation transcript's outputs.jsonl.
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

        if record_id not in transcript_index:
            raise UnknownRecordIdError(record_id)

        row = RawLabelRow.model_validate(raw)
        output_text: str = transcript_index[record_id]
        scorer_verdict: bool = judged_index[record_id]

        results.append(
            CalibrationLabel(
                record_id=row.record_id,
                scorer=row.scorer,
                output_text=output_text,
                scorer_verdict=scorer_verdict,
                pre_label=row.pre_label,
                pre_labeller_model=pre_labeller_model,
                human_verdict=None,
                adjudicated_at=None,
                notes=row.notes,
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


def _build_transcript_index(transcript_path: Path) -> dict[str, str]:
    """Build a record_id→output_text index from a generation transcript outputs.jsonl.

    Args:
        transcript_path: Path to the outputs.jsonl of a generation run.
    Returns:
        Dict mapping record_id to npc_response.
    Raises:
        FileNotFoundError: If the path does not exist.
    """
    index: dict[str, str] = {}
    for line in transcript_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        index[obj["record_id"]] = obj.get("npc_response", "")
    return index


def _build_judged_index(judged_path: Path) -> dict[str, bool]:
    """Build a record_id→scorer_verdict index from a judged.jsonl file.

    Args:
        judged_path: Path to the judged.jsonl of a judge/deterministic pass.
    Returns:
        Dict mapping record_id to the passed (scorer_verdict) bool.
    Raises:
        FileNotFoundError: If the path does not exist.
    """
    index: dict[str, bool] = {}
    for line in judged_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        index[obj["record_id"]] = bool(obj.get("passed", False))
    return index


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
        metavar="PATH",
        help="Path to the judged.jsonl (judge_runner or deterministic_pass output).",
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
    transcript_index = _build_transcript_index(args.transcript)
    judged_index = _build_judged_index(args.judged)

    new_labels = import_labels(raw_rows, transcript_index, judged_index, args.model)

    existing: list[CalibrationLabel] = []
    if args.append and args.out.exists():
        existing = read_calibration_labels(args.out)

    write_calibration_labels(args.out, existing + new_labels)
    print(f"Imported {len(new_labels)} label(s) → {args.out}", file=sys.stderr)
    return 0
