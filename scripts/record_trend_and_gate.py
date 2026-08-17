"""
Module: record_trend_and_gate
Layer: scripts (dev tooling)
Purpose: Glue between a completed generation run and the trend/regression
         gate (EVAL-P23.1/P23.2): assemble a TrendRow from a gen_dir's
         summary + calibration, append it, then check it against the
         previously-recorded baseline and exit non-zero on regression.
         The final two steps of scripts/Run-EvalHarness.ps1 (EVAL-P23.3).
Dependencies: argparse, pathlib, sys; evals/summary (summarize_from_dir),
         evals/calibration (run_calibration), evals/calibration_records
         (read_calibration_labels), evals/eval_records (read_transcript),
         evals/paired_stats (PairedResult — accepted, not computed here),
         evals/trend_store, evals/regression_gate
Used by: scripts/Run-EvalHarness.ps1 (EVAL-P23.3)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from calibration import run_calibration  # noqa: E402
from calibration_records import LABELS_FILE, read_calibration_labels  # noqa: E402
from eval_records import read_transcript  # noqa: E402
from regression_gate import check_regression, format_regression_report  # noqa: E402
from summary import summarize_from_dir  # noqa: E402
from trend_store import (  # noqa: E402
    TREND_STORE_FILE,
    RateWithCI,
    ScorerKappa,
    TrendRow,
    append_trend_row,
    latest_row,
)

_UNKNOWN_HARNESS_VERSION: str = "unknown"


def _rate_with_ci(rate: float | None, ci_low: float | None, ci_high: float | None, n: int) -> RateWithCI:
    """Build a RateWithCI, tolerating an unmeasured (all-None) rate."""
    return RateWithCI(rate=rate, ci_low=ci_low, ci_high=ci_high, n=n)


def _harness_version(gen_dir: Path) -> str:
    """Read harness_version from a gen_dir's meta.json, or a sentinel if absent."""
    transcript = read_transcript(gen_dir / "outputs.jsonl")
    if transcript.config is None:
        return _UNKNOWN_HARNESS_VERSION
    return transcript.config.harness_version


def build_trend_row(
    gen_id: str,
    gen_dir: Path,
    *,
    labels_path: Path = LABELS_FILE,
    recorded_at: str | None = None,
) -> TrendRow:
    """Assemble a TrendRow from a completed run's on-disk artifacts.

    Args:
        gen_id: The generation id this row records.
        gen_dir: Directory holding outputs.jsonl / judged.jsonl / deterministic_judged.jsonl.
        labels_path: Calibration labels file to compute per-scorer kappa from.
        recorded_at: ISO-8601 timestamp override (tests only); real callers
            omit this and get the current time.
    Returns:
        A TrendRow ready for trend_store.append_trend_row.
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

    return TrendRow(
        gen_id=gen_id,
        harness_version=_harness_version(gen_dir),
        recorded_at=recorded_at or datetime.now(timezone.utc).isoformat(),
        guard=_rate_with_ci(
            eval_summary.guard_rate, eval_summary.guard_ci_low, eval_summary.guard_ci_high,
            eval_summary.guard_turns,
        ),
        capability=_rate_with_ci(
            eval_summary.capability_rate, eval_summary.capability_ci_low, eval_summary.capability_ci_high,
            eval_summary.capability_turns,
        ),
        inconclusive_rate=inconclusive_rate,
        scorer_kappas=scorer_kappas,
    )


def main(argv: list[str] | None = None) -> int:
    """Record a trend row for a completed run, then gate on regression.

    Args:
        argv: Argument list; defaults to sys.argv[1:].
    Returns:
        0 when recorded and no regression fired; 1 when the gate fires;
        2 on a setup error (e.g. no prior baseline to compare against).
    """
    parser = argparse.ArgumentParser(
        description="Record a trend row for a completed eval run and gate on regression."
    )
    parser.add_argument("--gen-id", required=True, help="Generation id of the completed run.")
    parser.add_argument("--gen-dir", type=Path, required=True, help="Generation directory.")
    parser.add_argument("--trend-store", type=Path, default=TREND_STORE_FILE)
    parser.add_argument(
        "--allow-no-baseline", action="store_true",
        help="Exit 0 instead of 2 when the trend store has no prior row to gate against "
             "(expected on the very first recorded run).",
    )
    args = parser.parse_args(argv)

    baseline = latest_row(args.trend_store)
    row = build_trend_row(args.gen_id, args.gen_dir)
    append_trend_row(row, args.trend_store)
    print(f"Recorded trend row for gen_id={args.gen_id} -> {args.trend_store}")

    if baseline is None:
        print("No prior trend row to gate against.")
        return 0 if args.allow_no_baseline else 2

    report = check_regression(row, baseline)
    print(format_regression_report(report))
    return 1 if report.regressed else 0


if __name__ == "__main__":
    sys.exit(main())
