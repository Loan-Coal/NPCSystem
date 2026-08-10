"""
Module: oracle_adjudicate
Layer: scripts (dev tooling — not part of src/ or the evals package)
Purpose: Copy pre_label into human_verdict verbatim on an oracle labels file, so
         the HEADLINE calibration axis (scorer_verdict × human_verdict) is exactly
         the matrix scripts/oracle_labeller.py was asked for.
Dependencies: argparse, json, pathlib, sys
Used by: make mock-calibrate-oracle (EVAL-P15.1)
Does NOT: call any LLM, use randomness, or write to the real human labels file.

Why this exists rather than reusing scripts/mock_adjudicate.py: that script draws
human_verdict from scorer_verdict at a probability, so its matrix is random and
its diagonal is whatever the RNG produced. The oracle's whole value is that the
matrix is known BEFORE the pipeline runs, which requires human_verdict to be the
oracle's own pre_label with nothing in between. `--agree-rate 1.0` on the mock
adjudicator would set human_verdict = scorer_verdict, collapsing fp and fn to
zero — the opposite of what is wanted.

⚠️ These verdicts are synthetic. Every touched row is stamped
adjudicated_at='ORACLE' and its notes prefixed ORACLE:, so oracle rows are
greppable and can never be mistaken for human adjudication.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ORACLE_TIMESTAMP: str = "ORACLE"
_NOTE_PREFIX: str = "ORACLE:"
_REAL_LABELS_FILENAME: str = "labels_v1.jsonl"


class OracleAdjudicationError(Exception):
    """Raised when a row cannot be adjudicated by the identity rule.

    Attributes:
        record_id: The offending row's identifier.
        reason: Why the row was rejected.
    """

    def __init__(self, record_id: str, reason: str) -> None:
        self.record_id = record_id
        self.reason = reason
        super().__init__(f"Cannot oracle-adjudicate row {record_id!r}: {reason}")


def adjudicate_row(row: dict[str, Any]) -> dict[str, Any]:
    """Set human_verdict to the row's own pre_label.

    Args:
        row: One CalibrationLabel row as a dict.
    Returns:
        A new dict with human_verdict, adjudicated_at and notes set. The input
        is not mutated.
    Raises:
        OracleAdjudicationError: If pre_label is absent or not a bool — a
            defaulted verdict would fabricate a cell in the known matrix.
    """
    record_id = str(row.get("record_id", ""))
    pre_label = row.get("pre_label")
    if not isinstance(pre_label, bool):
        raise OracleAdjudicationError(record_id, f"pre_label is {pre_label!r}, expected a bool")

    notes = str(row.get("notes", ""))
    if not notes.startswith(_NOTE_PREFIX):
        notes = f"{_NOTE_PREFIX} {notes}".strip()
    return {**row, "human_verdict": pre_label, "adjudicated_at": ORACLE_TIMESTAMP, "notes": notes}


def adjudicate_file(path: Path) -> list[dict[str, Any]]:
    """Apply the identity rule to every row of a labels JSONL file.

    Args:
        path: Path to the labels JSONL written by label-import.
    Returns:
        Adjudicated rows in file order.
    Raises:
        FileNotFoundError: If the path does not exist.
        OracleAdjudicationError: If any row has no usable pre_label.
    """
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(adjudicate_row(json.loads(line)))
    return rows


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the oracle adjudicator."""
    p = argparse.ArgumentParser(
        prog="python scripts/oracle_adjudicate.py",
        description=(
            "Copy pre_label into human_verdict so the oracle's requested confusion "
            "matrix is what calibrate reports. NOT human adjudication."
        ),
    )
    p.add_argument("--labels", type=Path, required=True, metavar="PATH",
                   help="Oracle labels JSONL from label-import.")
    p.add_argument("--out", type=Path, required=True, metavar="PATH",
                   help="Destination adjudicated JSONL path.")
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the oracle adjudicator.

    Args:
        argv: Argument list; defaults to sys.argv[1:].
    Returns:
        0 on success.
    Raises:
        OracleAdjudicationError: If --out is the real human labels file, or any
            row has no usable pre_label.
    """
    args = _build_parser().parse_args(argv)
    if args.out.name == _REAL_LABELS_FILENAME or args.labels.name == _REAL_LABELS_FILENAME:
        raise OracleAdjudicationError(
            str(args.out), "that is the real human labels file; its verdicts cannot be regenerated"
        )

    rows = adjudicate_file(args.labels)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8"
    )
    print(
        f"Oracle-adjudicated {len(rows)} row(s) (human_verdict := pre_label) -> {args.out}\n"
        f"  Verdicts are synthetic; this file measures the pipeline, not a scorer.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
