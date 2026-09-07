"""
Module: judge_run_artifacts
Layer: evals (eval harness — not part of src/)
Purpose: Decide where a judge pass's side artifacts go and assemble the RunStatus
         it records. Split out of judge_runner.py to keep that module under the
         300-line cap; judge_runner keeps the scoring flow, this keeps the
         file-layout and status-reporting conventions in one place.
Dependencies: argparse, pathlib; panel_metrics (PanelMetrics),
         panel_metric_records (CriterionKappa, RepeatFlips), run_status
         (RunStatus, default_status_path, status_for, write_run_status)
Used by: judge_runner (main and _run_judging), scripts/migrate_panel_judged.py
         (with_panel_metrics — so a re-derived status records the same agreement
         fields a live pass does)
Does NOT: score records, read transcripts, import from src/npc_engine/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from panel_metric_records import CriterionKappa, RepeatFlips
from panel_metrics import PanelMetrics
from run_status import RunStatus, default_status_path, status_for, write_run_status

# Sibling of --json-out in panel mode: one row per seat per record, while
# --json-out itself keeps the one-row-per-record consensus shape (DEC-187).
PANEL_VOTES_FILENAME: str = "judged_panel_votes.jsonl"

# Exit code for a pass that could not complete, as opposed to one that completed
# with cases below target (1). See run_status.status_for and DEC-189.
_EXIT_ERROR: int = 2


def panel_votes_path(json_out: Path) -> Path:
    """Conventional sibling path for the per-seat vote rows of a panel run."""
    return json_out.parent / PANEL_VOTES_FILENAME


def status_path_for(args: argparse.Namespace) -> Path | None:
    """Resolve where run_status.json goes, or None when there is nowhere to put it.

    Args:
        args: Parsed CLI namespace carrying status_out and json_out.
    Returns:
        An explicit --status-out, else the conventional sibling of --json-out,
        else None when neither was given.
    """
    # argparse.Namespace attributes are Any; both branches are really Paths, so
    # construct explicitly rather than let an unchecked Any escape an annotated return.
    if args.status_out is not None:
        return Path(args.status_out)
    if args.json_out is not None:
        return Path(default_status_path(args.json_out))
    return None


def _criterion_kappas(metrics: PanelMetrics) -> tuple[CriterionKappa, ...]:
    """Map the per-judge_kind breakdown onto its persisted shape."""
    return tuple(
        CriterionKappa(
            judge_kind=c.judge_kind, kappa=c.kappa,
            n_items=c.n_items, unanimous=c.unanimous,
        )
        for c in metrics.by_criterion
    )


def _repeat_flips(metrics: PanelMetrics) -> RepeatFlips:
    """Map the engine-vs-judge flip decomposition onto its persisted shape."""
    flips = metrics.repeat_flips
    return RepeatFlips(
        records_with_flips=flips.records_with_flips,
        unanimous_flips=flips.unanimous_flips,
        solo_flips=flips.solo_flips,
        n_records=flips.n_records,
    )


def with_panel_metrics(status: RunStatus, metrics: PanelMetrics | None) -> RunStatus:
    """Return `status` carrying the panel's agreement statistics.

    The trend store reads these off run_status.json rather than re-joining the
    transcript with the votes file (DEC-189 frames this file as the per-run
    metrics record, and the judge pass already holds the PanelMetrics object).
    Kappa is recorded WITH its bootstrap interval: the instrument check needs
    the interval, and a point estimate alone cannot be gated on (DEC-185).

    Args:
        status: The status to extend.
        metrics: Panel statistics, or None for a single-judge pass.
    Returns:
        A new RunStatus (the model is frozen); `status` unchanged when metrics
        is None.
    """
    if metrics is None:
        return status
    return status.model_copy(
        update={
            "fleiss_kappa": metrics.kappa.kappa,
            "kappa_ci_low": metrics.kappa.ci_low,
            "kappa_ci_high": metrics.kappa.ci_high,
            "kappa_n_items": metrics.kappa.n_items,
            "kappa_by_criterion": _criterion_kappas(metrics),
            "repeat_flips": _repeat_flips(metrics),
            "raw_agreement": metrics.agreement.rate,
        }
    )


def build_status(
    exit_code: int,
    passed: int,
    total: int,
    panel_metrics: PanelMetrics | None,
    panel_models: tuple[str, ...],
    judge_model: str,
    report_path: Path | None,
    json_out: Path | None,
) -> RunStatus:
    """Assemble the RunStatus for a completed pass.

    Args:
        exit_code: 0 (gate met) or 1 (gate not met) — never the error code here.
        passed: Cases meeting their expectations.
        total: Cases evaluated.
        panel_metrics: Panel statistics, None for a single-judge pass; when
            present, every agreement field is filled in by with_panel_metrics.
        panel_models: Panel roster, empty for a single-judge pass.
        judge_model: Single-judge model name, empty for a panel pass.
        report_path: Markdown report this pass wrote; None when report
            rendering failed (ISSUE-288) — the judge pass still completed, so
            this is recorded as an empty path rather than refused.
        json_out: The --json-out path, used to locate the votes file.
    Returns:
        A RunStatus ready to write.
    """
    return with_panel_metrics(
        RunStatus(
            status=status_for(exit_code),
            cases_passed=passed,
            cases_total=total,
            judge_panel=panel_models,
            judge_model=judge_model,
            report_path=str(report_path) if report_path is not None else "",
            votes_path=str(panel_votes_path(json_out)) if (panel_models and json_out) else "",
        ),
        panel_metrics,
    )


def record_error(args: argparse.Namespace, message: str) -> int:
    """Print an error, write an 'error' run status when possible, return the error code.

    Args:
        args: Parsed CLI namespace, used to locate the status file.
        message: What went wrong; recorded verbatim so the morning handoff does
            not need log archaeology.
    Returns:
        The error exit code (2).
    """
    print(message, file=sys.stderr)
    path = status_path_for(args)
    if path is not None:
        write_run_status(RunStatus(status="error", error=message), path)
    return _EXIT_ERROR
