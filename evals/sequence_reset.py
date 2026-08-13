"""
Module: sequence_reset
Layer: evals (eval harness — not part of src/)
Purpose: Build the ResetFn the sequence runner calls before each repetition. Reads
         evals/reset_fidelity.json ONCE (EVAL-P12.4 validation: "reset_fidelity.json
         was read, not assumed") to learn what preconditions.reset_world structurally
         clears vs. leaves surviving, then times each live reset_world() call and
         reports that measured duration_ms in a fresh ResetReceipt per repetition.
Dependencies: json, pathlib, time (stdlib), httpx (via injected client), preconditions
              (evals/), reset_fidelity_record (evals/), sequence_records (evals/)
Used by: evals/sequence_rates.py (EVAL-P12.4)

Why cleared/surviving are not re-measured per repetition: EVAL-P12.1 already proved
(by full graph + in-process-store diff) that reset_world PATCHes exactly
world_state.epoch and world_state.active_conditions and nothing else — that is a
structural property of the endpoint, not something that varies run to run. Re-diffing
the whole graph on every one of k * 6 repetitions would dominate the wall-clock budget
for no new evidence. What DOES vary per call is timing, so duration_ms is measured live.
"""

from __future__ import annotations

import json
from pathlib import Path
from time import monotonic
from typing import Any

from preconditions import WorldBaseline, reset_world
from reset_fidelity_record import ResetFidelityReport
from sequence_records import ResetReceipt

_REPO_ROOT = Path(__file__).resolve().parent.parent
RESET_FIDELITY_JSON = _REPO_ROOT / "evals" / "reset_fidelity.json"

_MS_PER_S: int = 1000


def load_reset_fidelity_report(path: Path = RESET_FIDELITY_JSON) -> ResetFidelityReport:
    """Read and validate the EVAL-P12.1 measurement artifact.

    Args:
        path: Path to evals/reset_fidelity.json.
    Returns:
        The validated ResetFidelityReport.
    Raises:
        FileNotFoundError: If the artifact is missing — EVAL-P12.4 must not assume
            a fidelity tier it has not read.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist — run `make measure-reset-fidelity` (EVAL-P12.1) first. "
            "EVAL-P12.4 reads this artifact rather than assuming a fidelity tier."
        )
    return ResetFidelityReport.model_validate(json.loads(path.read_text(encoding="utf-8")))


def make_reset_fn(
    client: Any,
    base_url: str,
    baseline: WorldBaseline = WorldBaseline(),
    report: ResetFidelityReport | None = None,
):
    """Build a ResetFn that resets world state and returns a measured ResetReceipt.

    Args:
        client: Synchronous HTTP client (httpx.Client) with auth headers preset.
        base_url: API base URL.
        baseline: World-state baseline to reset to (epoch + active_conditions).
        report: Pre-loaded fidelity report; loaded from RESET_FIDELITY_JSON if None.
    Returns:
        A zero-argument callable matching sequence_runner.ResetFn: calls
        preconditions.reset_world, times it, and returns a ResetReceipt carrying
        the EVAL-P12.1-measured cleared/surviving sets and this call's live duration.
    """
    fidelity_report = report if report is not None else load_reset_fidelity_report()

    def _reset_fn() -> ResetReceipt:
        t0 = monotonic()
        reset_world(client, base_url, baseline)
        duration_ms = int((monotonic() - t0) * _MS_PER_S)
        return ResetReceipt(
            cleared=fidelity_report.cleared,
            surviving=fidelity_report.surviving,
            duration_ms=duration_ms,
        )

    return _reset_fn
