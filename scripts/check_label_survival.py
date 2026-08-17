"""
Module: check_label_survival
Layer: scripts (dev tooling)
Purpose: CLI wrapper around evals/label_survival.py — the freeze-gate check
         run before spending a regeneration or a labelling pass. Exits
         non-zero when any existing label would drift or lose its match
         against the candidate transcript.
Dependencies: argparse, pathlib, sys; evals/label_survival, evals/calibration_records
Used by: make check-label-survival, project-harness/ROADMAP.md Phase B3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from calibration_records import LABELS_FILE, read_calibration_labels  # noqa: E402
from label_survival import format_survival_report, simulate_survival  # noqa: E402

_DEFAULT_TRANSCRIPT = (
    Path(__file__).resolve().parents[1]
    / "evals"
    / "generations"
    / "k3_73e6c36"
    / "outputs.jsonl"
)


def _force_utf8_streams() -> None:
    """Reconfigure stdout so a report glyph cannot crash the check.

    Mirrors check_conservation.py's guard — same Windows cp1252 hazard.
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass  # Non-reconfigurable stream (pipe/pytest capture) — leave as-is.


def main(argv: Sequence[str] | None = None) -> int:
    """Parse args, simulate survival, print report, exit non-zero if not frozen.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).
    Returns:
        0 if every existing label survives (no drift, no orphaning); 1 otherwise.
    """
    _force_utf8_streams()
    parser = argparse.ArgumentParser(
        description=(
            "Freeze-gate check: does the labels file survive a candidate "
            "transcript unchanged? Run against the current transcript as a "
            "self-check, or against a freshly regenerated one before "
            "committing to it as the corpus a labelling pass will cover."
        )
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=LABELS_FILE,
        help=f"Labels file to check (default: {LABELS_FILE}).",
    )
    parser.add_argument(
        "--transcript",
        type=Path,
        default=_DEFAULT_TRANSCRIPT,
        help=f"Candidate transcript outputs.jsonl (default: {_DEFAULT_TRANSCRIPT}).",
    )
    args = parser.parse_args(argv)

    labels = read_calibration_labels(args.labels)
    report = simulate_survival(labels, args.transcript)
    print(format_survival_report(report))
    return 0 if report.is_frozen else 1


if __name__ == "__main__":
    sys.exit(main())
