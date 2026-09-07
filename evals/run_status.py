"""
Module: run_status
Layer: evals (eval harness — not part of src/)
Purpose: The machine-readable run_status.json an eval pass writes next to its
         artifacts, so ops scripts can tell "the quality gate was not met" apart
         from "the harness broke" without interpreting exit codes.
Dependencies: json, pathlib, typing, pydantic; panel_metric_records
         (PanelKappa, CriterionKappa, RepeatFlips)
Used by: judge_runner (writes it), project-harness overnight scripts (read it),
         scripts/record_trend_and_gate.py (reads the panel metrics off it when
         building a TrendRow, rather than re-joining the transcript with the
         votes file — DEC-189 already frames this file as the per-run metrics
         record, and the judge pass has the PanelMetrics object in hand)
Does NOT: call /v1/dialogue, modify graph state, import from src/npc_engine/

WHY THIS EXISTS (DEC-189)
On 2026-08-17 the overnight Phase 1 script read judge_runner's exit code 1 —
which means "the pass completed; 16 of 210 cases did not meet expectations" —
as an infra failure, wrote "Panel judge pass FAILED" into the morning handoff,
and halted Phase 2. The measurement had in fact succeeded completely. Exit codes
carry too little information to be read safely by a second program, and the
convention (0 ok / 1 gate / 2 error) lived only as tribal knowledge inside
judge_runner.main's docstring. This file makes the distinction explicit and
durable, and doubles as the per-run record for tracking metrics across A/B runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from panel_metric_records import CriterionKappa, PanelKappa, RepeatFlips

# Exit-code convention shared by the eval runners (judge_runner.main and peers).
_EXIT_OK: int = 0
_EXIT_GATE_FAILED: int = 1

RunStatusLiteral = Literal["ok", "gate_failed", "error"]

# The statuses under which the run's measurements are trustworthy. 'gate_failed'
# is included deliberately: cases failing IS the measurement, not a malfunction.
_VALID_MEASUREMENT_STATUSES: frozenset[str] = frozenset({"ok", "gate_failed"})


def status_for(exit_code: int) -> RunStatusLiteral:
    """Map a runner exit code onto an explicit status.

    Args:
        exit_code: 0 (all cases passed), 1 (some cases failed), anything else
            (the pass could not complete).
    Returns:
        'ok', 'gate_failed' or 'error'.
    """
    if exit_code == _EXIT_OK:
        return "ok"
    if exit_code == _EXIT_GATE_FAILED:
        return "gate_failed"
    return "error"


class RunStatus(BaseModel):
    """One eval pass's outcome, in a form another program can act on.

    Attributes:
        status: 'ok' (gate met), 'gate_failed' (ran fine, quality below target),
            'error' (did not complete — the only status that invalidates results).
        cases_passed: Cases meeting their expectations.
        cases_total: Cases evaluated.
        judge_panel: Panel roster, empty for a single-judge pass.
        judge_model: Single-judge model name, empty for a panel pass.
        fleiss_kappa: Chance-corrected inter-judge agreement, when a panel ran.
        kappa_ci_low: Lower bound of fleiss_kappa's cluster-bootstrap 95% CI.
        kappa_ci_high: Upper bound of that CI. The trend gate's instrument check
            needs the interval, not just the point estimate — a point comparison
            on a number whose CI spans [0.227, 0.730] fires on noise (DEC-185).
        kappa_n_items: Rateable items the kappa was computed over.
        kappa_by_criterion: Per-judge_kind breakdown; this is what localised
            refusal_judge at 0.225 against tone_judge at 1.000 (ISSUE-184).
        repeat_flips: Engine-vs-judge noise decomposition across repetitions.
        raw_agreement: Uncorrected pairwise agreement, when a panel ran. Kept
            below kappa, never as the headline (DEC-188).
        report_path: Path of the markdown report this pass wrote.
        votes_path: Path of the per-seat votes file, when a panel ran.
        duration_s: Wall-clock seconds the pass took, when measured.
        provenance: How this status was produced when it was not a live pass
            (e.g. re-derived from a legacy artifact). Empty for a normal run.
        error: Failure description. Set when status is 'error' (the pass did not
            complete). Also set — while status stays 'ok'/'gate_failed' — when
            judging completed but the markdown report could not be rendered
            (ISSUE-288, e.g. a guard-only generation with zero capability
            cases); report_path is "" in that case. Empty otherwise.
    """

    model_config = ConfigDict(frozen=True)

    status: RunStatusLiteral
    cases_passed: int = 0
    cases_total: int = 0
    judge_panel: tuple[str, ...] = ()
    judge_model: str = ""
    fleiss_kappa: float | None = None
    kappa_ci_low: float | None = None
    kappa_ci_high: float | None = None
    kappa_n_items: int = 0
    kappa_by_criterion: tuple[CriterionKappa, ...] = ()
    repeat_flips: RepeatFlips | None = None
    raw_agreement: float | None = None
    report_path: str = ""
    votes_path: str = ""
    duration_s: float | None = None
    provenance: str = ""
    error: str = Field(default="")

    @property
    def measurement_valid(self) -> bool:
        """Whether this run's numbers can be used.

        True for 'ok' and 'gate_failed' — a failed gate is a real measurement.
        False only for 'error'.
        """
        return self.status in _VALID_MEASUREMENT_STATUSES

    @property
    def panel_kappa(self) -> PanelKappa | None:
        """The overall kappa with its interval, or None when no panel ran.

        Assembled from the flat fields rather than stored twice, so a status
        file written before those fields existed still yields a usable (if
        interval-free) PanelKappa instead of nothing.
        """
        if self.fleiss_kappa is None:
            return None
        return PanelKappa(
            kappa=self.fleiss_kappa,
            ci_low=self.kappa_ci_low,
            ci_high=self.kappa_ci_high,
            n_items=self.kappa_n_items,
        )


def write_run_status(status: RunStatus, path: Path) -> Path:
    """Write a RunStatus to path as pretty-printed JSON.

    Args:
        status: The outcome to record.
        path: Destination .json file; parent directories are created.
    Returns:
        The path written, for logging.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(status.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def read_run_status(path: Path) -> RunStatus | None:
    """Load a run_status.json, or None when there is nothing usable there.

    Args:
        path: The run_status.json to read.
    Returns:
        The parsed RunStatus, or None when the file is absent, unreadable or
        does not parse. Degrading to None is deliberate and matches
        judge_identity's handling of the same file: a cosmetic problem in a
        side-artifact must not abort the trend recording of a real measurement.
        Callers that need the panel metrics report their absence explicitly
        (instrument_gate reports SKIPPED, never "stable").
    """
    if not path.exists():
        return None
    try:
        return RunStatus.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError):
        return None  # quality-ok: see the docstring — absence is reported, not swallowed


def default_status_path(json_out: Path) -> Path:
    """Derive the conventional run_status.json location beside a --json-out file."""
    return json_out.parent / "run_status.json"
