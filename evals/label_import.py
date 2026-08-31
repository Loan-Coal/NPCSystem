"""
Module: label_import
Layer: evals (eval harness — not part of src/)
Purpose: Validate and import a Claude-CLI labelling session into CalibrationLabel rows.
         Reads minimal JSONL (record_id, scorer, pre_label, notes), joins output_text,
         criteria, player_message, and observed from the transcript index and
         scorer_verdict from the judged index, stamps pre_labeller_model, and writes
         validated CalibrationLabel rows with human_verdict=None, then reconciles
         them against the existing labels file so no human verdict is ever lost.
         Split out to stay under the 300-line cap: transcript_index.py (index
         building, shared with label_export via export_item.py), label_import_errors.py
         (exception types), raw_label_rows.py (the labeller-side contract), and
         label_merge.py (no-clobber policy + reconciliation).
Dependencies: argparse, pathlib, sys, calibration_records, content_hash, export_item,
              transcript_index, label_import_errors, label_merge, raw_label_rows
Used by: python -m evals label-import; make label-import (EVAL-P5.6)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from calibration_records import (
    LABELS_FILE,
    CalibrationLabel,
    write_calibration_labels,
)
from content_hash import sha256_text
from export_item import ExportItem
from label_import_errors import (
    ContaminatedRowError,
    MissingVerdictError,
    UnknownRecordIdError,
)
from label_merge import format_merge_report, load_existing_or_refuse, merge_labels
from raw_label_rows import RawLabelRow, check_contamination, read_raw_rows
from record_identity import composite_item_id, split_item_id
from synthetic_label_guard import check_synthetic_label_target
from transcript_index import (
    build_judged_index,
    build_transcript_index,
    read_transcript_provenance,
)

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

_DEFAULT_PRE_LABELLER: str = "claude-opus-5"


# ---------------------------------------------------------------------------
# Core import logic
# ---------------------------------------------------------------------------


def import_labels(
    raw_rows: Sequence[dict[str, Any]],
    transcript_index: Mapping[str, ExportItem],
    judged_index: Mapping[str, bool],
    pre_labeller_model: str,
    gen_id: str = "",
    golden_set_version: str = "",
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
        gen_id: Generation the labels are bound to, recorded on each row so a
                label can never be silently attributed to a different run.
        golden_set_version: Case-set fingerprint at label time, same rationale.
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
        check_contamination(raw, record_id)

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
                gen_id=gen_id,
                golden_set_version=golden_set_version,
                output_sha256=sha256_text(export_item.output_text),
                criteria_sha256=sha256_text(export_item.criteria),
            )
        )
    return results


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
        "--merge",
        action="store_true",
        help=(
            "Reconcile with the existing labels file: refresh scorer_verdict and "
            "the transcript passthrough fields, preserve every human verdict. "
            "Use this after fixing a judge's criteria and re-running the judge."
        ),
    )
    p.add_argument(
        "--force-overwrite",
        action="store_true",
        help=(
            "Discard the existing labels file, including any human verdicts it "
            "holds. Refused by default; a backup .bak is still written."
        ),
    )
    p.add_argument(
        "--replace-pre-label",
        action="store_true",
        help=(
            "Overwrite existing rows' pre_label/pre_labeller_model with this "
            "import's values, for every matched row (not just drifted ones). "
            "Use this to import a genuine second-rater pass (e.g. Opus, "
            "EVAL-P22.3) over rows that already carry a pre_label — the "
            "default --merge behaviour preserves the existing pre_label "
            "untouched, which would silently discard the new opinion. Never "
            "affects human_verdict."
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the label-import verb.

    Args:
        argv: Argument list; defaults to sys.argv[1:].
    Returns:
        0 on success, 1 on error.
    Raises:
        SyntheticLabelTargetError: If a mock/oracle --model is aimed at the real
            human labels file. Checked before any input is read, so a refused
            run cannot have begun writing.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    check_synthetic_label_target(args.model, args.out)

    raw_rows = read_raw_rows(args.raw)
    transcript_index = build_transcript_index(args.transcript)

    judged_index: dict[str, bool] = {}
    for judged_path in args.judged:
        judged_index.update(build_judged_index(judged_path))

    gen_id, golden_set_version = read_transcript_provenance(args.transcript)
    new_labels = import_labels(
        raw_rows,
        transcript_index,
        judged_index,
        args.model,
        gen_id=gen_id,
        golden_set_version=golden_set_version,
    )
    existing = load_existing_or_refuse(
        args.out, allow_merge=args.merge, allow_overwrite=args.force_overwrite
    )

    if existing and args.merge:
        result = merge_labels(existing, new_labels, replace_pre_label=args.replace_pre_label)
        write_calibration_labels(args.out, result.rows)
        print(format_merge_report(result, args.out, len(new_labels)), file=sys.stderr)
        return 0

    write_calibration_labels(args.out, new_labels)
    print(f"Imported {len(new_labels)} label(s) → {args.out}", file=sys.stderr)
    return 0
