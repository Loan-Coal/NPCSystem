"""
Module: sequence_runner
Layer: evals (eval harness — not part of src/)
Purpose: Run one promoted scenario k times with world reset before each repetition,
         recording per-repetition outcome, wall-clock duration, and reset cost.
         Aggregates into CaseStat so flakiness classification comes free.
Dependencies: time (stdlib), typing, pydantic, case_stats, rate_stats (evals/)
Used by: evals/sequence_rates.py (EVAL-P12.4)
Does NOT: import from src/npc_engine/, call the NPC engine directly.
"""

from __future__ import annotations

import time
from typing import Callable

from pydantic import BaseModel, ConfigDict

from case_stats import CaseStat, classify
from rate_stats import pass_rate, wilson_interval

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ScenarioFn = Callable[[], bool]
ResetFn = Callable[[], None]

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
        reset_cost_ms: Wall-clock milliseconds for the reset that preceded this run.
        error: Exception message if the scenario raised; None on clean completion.
    """

    model_config = ConfigDict(frozen=True)

    repetition: int
    passed: bool
    duration_ms: int
    reset_cost_ms: int
    error: str | None = None


class SequenceResult(BaseModel):
    """Aggregated result of k scenario repetitions for one scenario.

    Attributes:
        scenario_id: Canonical scenario identifier.
        k: Number of repetitions requested.
        repetitions: One RepetitionRecord per run, in order.
        stat: CaseStat aggregated over all repetitions for flakiness classification.
    """

    model_config = ConfigDict(frozen=True)

    scenario_id: str
    k: int
    repetitions: tuple[RepetitionRecord, ...]
    stat: CaseStat


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _timed_reset(reset_fn: ResetFn) -> int:
    """Call reset_fn and return the wall-clock cost in milliseconds.

    Args:
        reset_fn: Callable that resets world state before the next repetition.
    Returns:
        Elapsed milliseconds as a non-negative integer.
    """
    t0 = time.monotonic()
    reset_fn()
    return int((time.monotonic() - t0) * _MS_PER_S)


def _run_one(repetition: int, scenario_fn: ScenarioFn, reset_cost_ms: int) -> RepetitionRecord:
    """Run one scenario repetition and capture timing and outcome.

    A scenario that raises is recorded as a failed repetition; the exception is
    caught and stored rather than re-raised so the remaining repetitions execute.

    Args:
        repetition: Zero-based index of this run within the k-set.
        scenario_fn: Callable that runs the scenario and returns True if passed.
        reset_cost_ms: Pre-measured cost of the reset that preceded this run.
    Returns:
        RepetitionRecord with outcome, timing, reset cost, and any error message.
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
        reset_cost_ms=reset_cost_ms,
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
    repetition rather than aborting the sequence.

    Args:
        scenario_id: Canonical scenario identifier, used as the CaseStat case_id.
        scenario_fn: Callable executed once per repetition; True return = pass.
        reset_fn: Callable that resets world state before each repetition.
        k: Number of repetitions to run (must be >= 1).
    Returns:
        SequenceResult containing one RepetitionRecord per run and a CaseStat.
    Raises:
        ValueError: When k < 1.
    """
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")

    records: list[RepetitionRecord] = []
    for i in range(k):
        reset_cost = _timed_reset(reset_fn)
        record = _run_one(i, scenario_fn, reset_cost)
        records.append(record)

    passes = sum(1 for r in records if r.passed)
    rate = pass_rate(passes, k)
    ci_low, ci_high = wilson_interval(passes, k)
    stat = CaseStat(
        case_id=scenario_id,
        k=k,
        passes=passes,
        pass_rate=rate,
        ci_low=ci_low,
        ci_high=ci_high,
        classification=classify(passes, k),
    )
    return SequenceResult(
        scenario_id=scenario_id,
        k=k,
        repetitions=tuple(records),
        stat=stat,
    )
