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
Dependencies: argparse, pathlib, sys; evals/summary (summarize_from_dir),
         evals/calibration (run_calibration), evals/calibration_records
         (read_calibration_labels), evals/eval_records (read_transcript),
         evals/paired_stats (PairedResult — accepted, not computed here),
         evals/run_status (read_run_status), evals/baseline_selection,
         evals/instrument_gate, evals/trend_store, evals/regression_gate
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
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from baseline_selection import (  # noqa: E402
    BaselineChoice,
    format_baseline_choice,
    select_baseline,
    select_named_baseline,
)
from calibration import run_calibration  # noqa: E402
from calibration_records import LABELS_FILE, read_calibration_labels  # noqa: E402
from eval_records import read_transcript  # noqa: E402
from instrument_gate import check_instrument, format_instrument_report  # noqa: E402
from regression_gate import check_regression, format_regression_report  # noqa: E402
from run_status import RunStatus, read_run_status  # noqa: E402
from summary import summarize_from_dir  # noqa: E402
from trend_store import (  # noqa: E402
    TREND_STORE_FILE,
    RateWithCI,
    ScorerKappa,
    TrendRow,
    append_trend_row,
    read_trend_rows,
)

_UNKNOWN_HARNESS_VERSION: str = "unknown"
_RUN_STATUS_FILENAME: str = "run_status.json"
_TRANSCRIPT_FILENAME: str = "outputs.jsonl"

_EXIT_OK: int = 0
_EXIT_REGRESSION: int = 1
_EXIT_SETUP_ERROR: int = 2
_EXIT_INSTRUMENT_DEGRADED: int = 3


def _rate_with_ci(rate: float | None, ci_low: float | None, ci_high: float | None, n: int) -> RateWithCI:
    """Build a RateWithCI, tolerating an unmeasured (all-None) rate."""
    return RateWithCI(rate=rate, ci_low=ci_low, ci_high=ci_high, n=n)


def _harness_version(gen_dir: Path) -> str:
    """Read harness_version from a gen_dir's meta.json, or a sentinel if absent."""
    transcript = read_transcript(gen_dir / _TRANSCRIPT_FILENAME)
    if transcript.config is None:
        return _UNKNOWN_HARNESS_VERSION
    return transcript.config.harness_version


def _panel_status(gen_dir: Path, status_path: Path | None) -> RunStatus | None:
    """Load the judge pass's run_status.json, or None when it isn't there.

    The panel's agreement statistics are read off this file rather than
    recomputed by re-joining outputs.jsonl with judged_panel_votes.jsonl: the
    judge pass already did that join and wrote the result (DEC-189), and
    duplicating it would let the two drift apart the way judged.jsonl's two
    writers did (DEC-187).
    """
    return read_run_status(status_path or gen_dir / _RUN_STATUS_FILENAME)


def build_trend_row(
    gen_id: str,
    gen_dir: Path,
    *,
    labels_path: Path = LABELS_FILE,
    recorded_at: str | None = None,
    status_path: Path | None = None,
) -> TrendRow:
    """Assemble a TrendRow from a completed run's on-disk artifacts.

    Args:
        gen_id: The generation id this row records.
        gen_dir: Directory holding outputs.jsonl / judged.jsonl / deterministic_judged.jsonl.
        labels_path: Calibration labels file to compute per-scorer kappa from.
        recorded_at: ISO-8601 timestamp override (tests only); real callers
            omit this and get the current time.
        status_path: run_status.json override; defaults to gen_dir's own.
    Returns:
        A TrendRow ready for trend_store.append_trend_row. Panel agreement is
        recorded chance-corrected (kappa with its interval, per criterion, plus
        the repeat-flip split) as well as raw — raw pairwise agreement alone is
        inflated by the pass base rate (DEC-188).
    """
    eval_summary = summarize_from_dir(gen_dir)
    inconclusive_rate = (
        eval_summary.inconclusive_failures / eval_summary.evaluated_cases
        if eval_summary.evaluated_cases > 0
        else None
    )

    labels = read_calibration_labels(labels_path) if labels_path.exists() else []
    reports = run_calibration(labels, print_fn=lambda *_a, **_k: None) if labels else []
    scorer_kappas = tuple(
        ScorerKappa(scorer=r.scorer, kappa=r.kappa, ci_low=r.kappa_lo, ci_high=r.kappa_hi, n=r.counts.n)
        for r in reports
    )
    status = _panel_status(gen_dir, status_path)

    return TrendRow(
        gen_id=gen_id,
        harness_version=_harness_version(gen_dir),
        recorded_at=recorded_at or datetime.now(timezone.utc).isoformat(),
        guard=_rate_with_ci(
            eval_summary.guard_rate, eval_summary.guard_ci_low, eval_summary.guard_ci_high,
            eval_summary.guard_turns,
        ),
        capability=_rate_with_ci(
            eval_summary.capability_rate, eval_summary.capability_ci_low,
            eval_summary.capability_ci_high, eval_summary.capability_turns,
        ),
        inconclusive_rate=inconclusive_rate,
        scorer_kappas=scorer_kappas,
        panel_agreement_rate=status.raw_agreement if status else None,
        panel_kappa=status.panel_kappa if status else None,
        kappa_by_criterion=status.kappa_by_criterion if status else (),
        repeat_flips=status.repeat_flips if status else None,
    )


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
    return parser


def _resolve(candidate_harness_version: str, requested_gen_id: str, store: Path) -> BaselineChoice:
    """Resolve the baseline for a run: the named row, or the latest comparable one."""
    rows = read_trend_rows(store)
    if requested_gen_id:
        return select_named_baseline(requested_gen_id, candidate_harness_version, rows)
    return select_baseline(candidate_harness_version, rows)


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
    transcript = args.gen_dir / _TRANSCRIPT_FILENAME
    if not transcript.exists():
        print(f"Transcript not found: {transcript}", file=sys.stderr)
        return _EXIT_SETUP_ERROR
    choice = _resolve(_harness_version(args.gen_dir), args.baseline_gen_id, args.trend_store)
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

    row = build_trend_row(args.gen_id, args.gen_dir)
    # Resolved BEFORE appending: afterwards the candidate is itself the most
    # recent comparable row, and a run would gate against itself.
    choice = _resolve(row.harness_version, args.baseline_gen_id, args.trend_store)
    append_trend_row(row, args.trend_store)
    print(f"Recorded trend row for gen_id={args.gen_id} -> {args.trend_store}")
    print(format_baseline_choice(choice, row.recorded_at))

    if choice.row is None:
        return _EXIT_OK if args.allow_no_baseline else _EXIT_SETUP_ERROR
    return _gate(row, choice.row)


if __name__ == "__main__":
    sys.exit(main())
