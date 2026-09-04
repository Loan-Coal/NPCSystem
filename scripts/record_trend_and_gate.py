"""
Module: record_trend_and_gate
Layer: scripts (dev tooling)
Purpose: Glue between a completed generation run and the trend/regression
         gate (EVAL-P23.1/P23.2): assemble a TrendRow from a gen_dir's
         summary + calibration + run_status, append it, resolve the baseline it
         is comparable with, then check it against that baseline and exit
         non-zero on a regression. The final two steps of
         scripts/Run-EvalHarness.ps1 (EVAL-P23.3), plus the --print-baseline
         resolution that harness calls BEFORE its compare step so both steps
         report on the same pair (EVAL-P23 Defect A).
Dependencies: argparse, pathlib, sys; evals/trend_row_builder (build_trend_row,
         comparability_key), evals/baseline_selection, evals/comparability
         (ComparabilityKey, key_for), evals/instrument_gate, evals/trend_store,
         evals/regression_gate
Used by: scripts/Run-EvalHarness.ps1 (EVAL-P23.3)

EXIT CODES (four states, not three — EVAL-P23 Defect E)
    0  recorded, no regression
    1  the engine regressed (a published rate, McNemar, or the inconclusive rate)
    2  setup error — nothing comparable to gate against
    3  the INSTRUMENT degraded: inter-judge agreement fell, so this run's rate
       comparison is not trustworthy and the engine is not necessarily at fault
Code 3 takes precedence over 1: when the ruler moved, a rate finding beside it
cannot be read as an engine result. Both reports are still printed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from baseline_selection import (  # noqa: E402
    BaselineChoice,
    format_baseline_choice,
    select_baseline,
    select_named_baseline,
)
from comparability import ComparabilityKey, key_for  # noqa: E402
from instrument_gate import check_instrument, format_instrument_report  # noqa: E402
from regression_gate import check_regression, format_regression_report  # noqa: E402
from trend_row_builder import (  # noqa: E402
    TRANSCRIPT_FILENAME,
    build_trend_row,
    comparability_key,
)
from trend_store import (  # noqa: E402
    TREND_STORE_FILE,
    TrendRow,
    append_trend_row,
    read_trend_rows,
)

_EXIT_OK: int = 0
_EXIT_REGRESSION: int = 1
_EXIT_SETUP_ERROR: int = 2
_EXIT_INSTRUMENT_DEGRADED: int = 3


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for recording a trend row and gating on it."""
    parser = argparse.ArgumentParser(
        description="Record a trend row for a completed eval run and gate on regression."
    )
    parser.add_argument("--gen-id", required=True, help="Generation id of the completed run.")
    parser.add_argument("--gen-dir", type=Path, required=True, help="Generation directory.")
    parser.add_argument("--trend-store", type=Path, default=TREND_STORE_FILE)
    parser.add_argument(
        "--baseline-gen-id", default="",
        help="Gate against this trend row specifically instead of the most recent "
             "comparable one. Refused if it is absent or was recorded under a "
             "different harness_version — naming a baseline cannot make it comparable.",
    )
    parser.add_argument(
        "--print-baseline", action="store_true",
        help="Print the gen_id of the row this run WOULD be gated against (empty "
             "line when there is none) and exit 0, recording nothing. The harness "
             "resolves the baseline once with this and passes it to both its "
             "compare step and its gate, so the two describe the same pair.",
    )
    parser.add_argument(
        "--allow-no-baseline", action="store_true",
        help="Exit 0 instead of 2 when the trend store holds no comparable prior "
             "row to gate against (expected on the very first recorded run, and "
             "after a harness_version change).",
    )
    parser.add_argument(
        "--allow-foreign-labels", action="store_true",
        help="Record the row even when its calibration labels name a different "
             "generation than --gen-id. Refused by default (see "
             "trend_store.LabelsGenerationMismatchError) — a row's kappas silently "
             "attributed to another run's labels is a real defect, not an edge case.",
    )
    return parser


def _resolve(key: ComparabilityKey, requested_gen_id: str, store: Path) -> BaselineChoice:
    """Resolve the baseline for a run: the named row, or the latest comparable one."""
    rows = read_trend_rows(store)
    if requested_gen_id:
        return select_named_baseline(requested_gen_id, key, rows)
    return select_baseline(key, rows)


def _print_baseline(args: argparse.Namespace) -> int:
    """Print the baseline gen_id this run would be gated against, and nothing else.

    Args:
        args: Parsed CLI namespace.
    Returns:
        0 always when the gen_dir is readable — an empty line is a valid answer
        meaning "there is no comparable baseline, skip the compare step". The
        line is kept machine-readable (the id alone) because PowerShell captures
        it as a value; the human-readable naming happens at gate time.
    """
    transcript = args.gen_dir / TRANSCRIPT_FILENAME
    if not transcript.exists():
        print(f"Transcript not found: {transcript}", file=sys.stderr)
        return _EXIT_SETUP_ERROR
    choice = _resolve(comparability_key(args.gen_dir), args.baseline_gen_id, args.trend_store)
    print(choice.row.gen_id if choice.row is not None else "")
    return _EXIT_OK


def _gate(row: TrendRow, baseline: TrendRow) -> int:
    """Run both gates against the chosen baseline and return the run's exit code.

    Args:
        row: The candidate run's freshly recorded trend row.
        baseline: The comparable baseline row.
    Returns:
        3 when the instrument degraded (checked first: a kappa drop means the
        rate comparison beside it cannot be read as an engine result), 1 when
        the engine regressed, 0 otherwise. Both reports print either way.
    """
    instrument = check_instrument(row, baseline)
    print(format_instrument_report(instrument))
    report = check_regression(row, baseline)
    print(format_regression_report(report))
    if instrument.degraded:
        return _EXIT_INSTRUMENT_DEGRADED
    return _EXIT_REGRESSION if report.regressed else _EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Record a trend row for a completed run, then gate on regression.

    Args:
        argv: Argument list; defaults to sys.argv[1:].
    Returns:
        0 recorded and clean, 1 engine regression, 2 setup error (nothing
        comparable to gate against), 3 instrument degraded. See the module
        docstring for the full contract.
    """
    args = _build_parser().parse_args(argv)
    if args.print_baseline:
        return _print_baseline(args)

    row = build_trend_row(
        args.gen_id, args.gen_dir, allow_foreign_labels=args.allow_foreign_labels,
    )
    # Resolved BEFORE appending: afterwards the candidate is itself the most
    # recent comparable row, and a run would gate against itself.
    choice = _resolve(key_for(row), args.baseline_gen_id, args.trend_store)
    append_trend_row(row, args.trend_store)
    print(f"Recorded trend row for gen_id={args.gen_id} -> {args.trend_store}")
    print(format_baseline_choice(choice, row.recorded_at))

    if choice.row is None:
        return _EXIT_OK if args.allow_no_baseline else _EXIT_SETUP_ERROR
    return _gate(row, choice.row)


if __name__ == "__main__":
    sys.exit(main())
