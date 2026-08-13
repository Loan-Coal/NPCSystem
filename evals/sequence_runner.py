"""
Module: sequence_runner
Layer: evals (eval harness — not part of src/)
Purpose: Run one promoted scenario k times with world reset before each repetition,
         recording per-repetition outcome, wall-clock duration, and the reset's
         ResetReceipt. Aggregates into a fidelity-gated SequenceStat so a PARTIAL
         reset can never surface a Wilson interval (ISSUE-143).
Dependencies: time (stdlib), typing, pydantic, sequence_fidelity, sequence_records (evals/)
Used by: evals/sequence_rates.py (EVAL-P12.4)
Does NOT: import from src/npc_engine/, call the NPC engine directly.
"""

from __future__ import annotations

import time
from typing import Callable

from pydantic import BaseModel, ConfigDict

from sequence_fidelity import SequenceStat, sequence_stat
from sequence_records import ResetReceipt

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ScenarioFn = Callable[[], bool]
# reset_fn's contract (EVAL-P12.4, Part A / ISSUE-143): it must return the evidence
# of what it actually cleared, not a bare cost. sequence_fidelity derives the run's
# tier from these receipts; a reset_fn that fabricates an empty `surviving` tuple
# lies about fidelity, so callers must build receipts from measured evidence
# (see evals/sequence_reset.py, which reads evals/reset_fidelity.json rather than
# assuming it).
ResetFn = Callable[[], ResetReceipt]

_MS_PER_S: int = 1000

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RepetitionRecord(BaseModel):
    """Outcome of a single scenario repetition.

    Attributes:
        repetition: Zero-based repeat index within the k-run set.
        passed: Whether the scenario returned True this repetition.
        duration_ms: Wall-clock milliseconds for the scenario call.
        reset_receipt: Evidence of what the reset preceding this repetition
            actually cleared and what survived it.
        error: Exception message if the scenario raised; None on clean completion.
    """

    model_config = ConfigDict(frozen=True)

    repetition: int
    passed: bool
    duration_ms: int
    reset_receipt: ResetReceipt
    error: str | None = None


class SequenceResult(BaseModel):
    """Aggregated result of k scenario repetitions for one scenario.

    Attributes:
        scenario_id: Canonical scenario identifier.
        k: Number of repetitions requested.
        repetitions: One RepetitionRecord per run, in order.
        stat: Fidelity-gated SequenceStat aggregated over all repetitions.
    """

    model_config = ConfigDict(frozen=True)

    scenario_id: str
    k: int
    repetitions: tuple[RepetitionRecord, ...]
    stat: SequenceStat


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_one(repetition: int, scenario_fn: ScenarioFn, reset_receipt: ResetReceipt) -> RepetitionRecord:
    """Run one scenario repetition and capture timing and outcome.

    A scenario that raises is recorded as a failed repetition; the exception is
    caught and stored rather than re-raised so the remaining repetitions execute.

    Args:
        repetition: Zero-based index of this run within the k-set.
        scenario_fn: Callable that runs the scenario and returns True if passed.
        reset_receipt: Evidence of what the preceding reset cleared and left surviving.
    Returns:
        RepetitionRecord with outcome, timing, reset receipt, and any error message.
    """
    t0 = time.monotonic()
    error: str | None = None
    passed = False
    try:
        passed = scenario_fn()
    except Exception as exc:  # intentional: record-not-abort contract
        error = str(exc)
    duration_ms = int((time.monotonic() - t0) * _MS_PER_S)
    return RepetitionRecord(
        repetition=repetition,
        passed=passed,
        duration_ms=duration_ms,
        reset_receipt=reset_receipt,
        error=error,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_sequence(
    scenario_id: str,
    scenario_fn: ScenarioFn,
    reset_fn: ResetFn,
    k: int,
) -> SequenceResult:
    """Run scenario_fn k times with reset_fn called before each repetition.

    The reset is called exactly k times — once before each run — and never
    after the last repetition. A scenario that raises is recorded as a failed
    repetition rather than aborting the sequence. The run's fidelity tier is
    derived from the k ResetReceipts and gates whether `stat.interval` is
    populated (ISSUE-143 / SEQUENCE_STATS_POLICY.md §3).

    Args:
        scenario_id: Canonical scenario identifier, used as the SequenceStat scenario_id.
        scenario_fn: Callable executed once per repetition; True return = pass.
        reset_fn: Callable that resets world state before each repetition and
            returns a ResetReceipt describing what it actually cleared.
        k: Number of repetitions to run (must be >= 1).
    Returns:
        SequenceResult containing one RepetitionRecord per run and a fidelity-gated stat.
    Raises:
        ValueError: When k < 1.
    """
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")

    records: list[RepetitionRecord] = []
    for i in range(k):
        reset_receipt = reset_fn()
        record = _run_one(i, scenario_fn, reset_receipt)
        records.append(record)

    passes = sum(1 for r in records if r.passed)
    stat = sequence_stat(scenario_id, passes, tuple(r.reset_receipt for r in records))
    return SequenceResult(
        scenario_id=scenario_id,
        k=k,
        repetitions=tuple(records),
        stat=stat,
    )
