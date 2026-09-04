"""
Module: check_label_adequacy
Layer: scripts (dev tooling)
Purpose: CLI wrapper around evals/label_adequacy.py — reports, per scorer, whether
         its human labels clear the count floor a kappa estimate needs (DEC-260).
         Exits non-zero when any scorer in the labels file is refused, so the check
         is usable as a standalone gate even though it is not wired into `make check`
         (see the Makefile comment on check-label-adequacy for why).
Dependencies: argparse, pathlib, sys; evals/label_adequacy, evals/calibration_records
Used by: make check-label-adequacy
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from calibration_records import LABELS_FILE, read_calibration_labels  # noqa: E402
from label_adequacy import check_label_adequacy  # noqa: E402


def _force_utf8_streams() -> None:
    """Reconfigure stdout so a report glyph cannot crash the check.

    Mirrors check_label_survival.py's guard — same Windows cp1252 hazard.
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass  # Non-reconfigurable stream (pipe/pytest capture) — leave as-is.


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the label-adequacy report."""
    parser = argparse.ArgumentParser(
        description=(
            "Per-scorer report: do this labels file's human verdicts clear the "
            "count floor a kappa estimate needs? Read-only — never writes to "
            "the labels file, which is frozen (scripts/loop_gates.py)."
        )
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=LABELS_FILE,
        help=f"Labels file to check (default: {LABELS_FILE}).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse args, check every scorer's labels, print a report, exit non-zero on any refusal.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).
    Returns:
        0 if every scorer's labels clear the floor; 1 if any scorer is refused.
    """
    _force_utf8_streams()
    args = _build_parser().parse_args(argv)

    rows = read_calibration_labels(args.labels)
    scorers = sorted({r.scorer for r in rows})
    refused = 0
    for scorer in scorers:
        refusal = check_label_adequacy(scorer, rows)
        if refusal is None:
            print(f"  OK       {scorer}")
        else:
            print(f"  REFUSED  {scorer}: {refusal.reason}")
            refused += 1

    if refused:
        print(f"FAIL - {refused} of {len(scorers)} scorer(s) refused (see docs/SCORER_TRUST_POLICY.md).")
        return 1
    print(f"OK - all {len(scorers)} scorer(s) clear the label-adequacy floor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
