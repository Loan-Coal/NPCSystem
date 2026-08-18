"""
Module: judge_run_artifacts
Layer: evals (eval harness — not part of src/)
Purpose: Decide where a judge pass's side artifacts go and assemble the RunStatus
         it records. Split out of judge_runner.py to keep that module under the
         300-line cap; judge_runner keeps the scoring flow, this keeps the
         file-layout and status-reporting conventions in one place.
Dependencies: argparse, pathlib; panel_metrics (PanelMetrics), run_status
         (RunStatus, default_status_path, status_for, write_run_status)
Used by: judge_runner (main and _run_judging)
Does NOT: score records, read transcripts, import from src/npc_engine/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
    if args.status_out is not None:
        return args.status_out
    if args.json_out is not None:
        return default_status_path(args.json_out)
    return None


def build_status(
    exit_code: int,
    passed: int,
    total: int,
    panel_metrics: PanelMetrics | None,
    panel_models: tuple[str, ...],
    judge_model: str,
    report_path: Path,
    json_out: Path | None,
) -> RunStatus:
    """Assemble the RunStatus for a completed pass.

    Args:
        exit_code: 0 (gate met) or 1 (gate not met) — never the error code here.
        passed: Cases meeting their expectations.
        total: Cases evaluated.
        panel_metrics: Panel statistics, None for a single-judge pass.
        panel_models: Panel roster, empty for a single-judge pass.
        judge_model: Single-judge model name, empty for a panel pass.
        report_path: Markdown report this pass wrote.
        json_out: The --json-out path, used to locate the votes file.
    Returns:
        A RunStatus ready to write.
    """
    return RunStatus(
        status=status_for(exit_code),
        cases_passed=passed,
        cases_total=total,
        judge_panel=panel_models,
        judge_model=judge_model,
        fleiss_kappa=panel_metrics.kappa.kappa if panel_metrics else None,
        raw_agreement=panel_metrics.agreement.rate if panel_metrics else None,
        report_path=str(report_path),
        votes_path=str(panel_votes_path(json_out)) if (panel_models and json_out) else "",
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
