"""
Module: probe_runner
Layer: evals (eval harness — not part of src/)
Purpose: Run one EngineProbe k times — reset, setup, drive, measure, check
         invariants — recording a RepetitionRecord (numeric metrics plus
         pass/fail) per repetition, aggregated into the same fidelity-gated
         SequenceStat the promoted scenarios get from sequence_fidelity.py,
         reused here rather than rebuilt. Also exposes read_engine_status: a
         standalone GET /v1/clock/state snapshot of every tick-registered
         engine's tick_count/error_count/duration_ms — free liveness and
         timing for all 46 engines whether or not a probe exists for them.
         `python -m evals probe` (VERBS["probe"]) is this module's main().
Dependencies: argparse, time (stdlib), httpx, pydantic, probe_protocol,
              sequence_fidelity, sequence_reset, sequence_runner, and every
              probe_<engine>.py module's *_PROBE_FACTORIES dict (evals/)
Used by: evals/__main__.py ("probe" verb), Makefile eval-probe target
Does NOT: import from src/npc_engine/, call the NPC engine directly — HTTP only,
          through the injected client, matching scenario_adapters*.py's convention.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Callable

import httpx
from pydantic import BaseModel, ConfigDict

from probe_dialogue import DIALOGUE_PROBE_FACTORIES
from probe_events import EVENTS_PROBE_FACTORIES
from probe_gossip import GOSSIP_PROBE_FACTORIES
from probe_legacy_adapters import LEGACY_PROBE_FACTORIES
from probe_memory import MEMORY_PROBE_FACTORIES
from probe_protocol import EngineProbe
from probe_quest import QUEST_PROBE_FACTORIES
from sequence_fidelity import SequenceStat, sequence_stat
from sequence_records import ResetReceipt
from sequence_reset import make_reset_fn
from sequence_runner import RepetitionRecord, ResetFn

_DEFAULT_K: int = 3
_DEFAULT_TICKS: int = 1
_DEFAULT_BASE_URL: str = "http://localhost:8000"
_MS_PER_S: int = 1000

# Phase 3 left this empty by design; Phase 4 (DEC-271) populates it by merging each
# per-engine probe module's own factory dict — the same composition pattern
# scenario_adapters.py already uses for EXTRA_SCENARIO_ADAPTER_FACTORIES. `main` already
# iterates it, so a later probe module needs no CLI change (OCP) — only this merge.
ProbeFactory = Callable[[httpx.Client], EngineProbe]
PROBE_FACTORIES: dict[str, ProbeFactory] = {
    **LEGACY_PROBE_FACTORIES,
    **GOSSIP_PROBE_FACTORIES,
    **EVENTS_PROBE_FACTORIES,
    **MEMORY_PROBE_FACTORIES,
    **QUEST_PROBE_FACTORIES,
    **DIALOGUE_PROBE_FACTORIES,
}


# ---------------------------------------------------------------------------
# Free per-engine liveness/timing (independent of any registered probe)
# ---------------------------------------------------------------------------


class EngineStatusSnapshot(BaseModel):
    """One engine's status record as read from GET /v1/clock/state's engine_status.

    Mirrors npc_engine.scheduler.engine_status_store.EngineStatusRecord's field
    names verbatim. Defined here rather than imported, because evals/ validates
    the engine's response contract on receipt rather than importing the source
    model — engine_adapter.py is the only sanctioned npc_engine import point
    (DEC-147 §2), and this is an HTTP response shape, not one.

    Attributes:
        tick_count: Total runs recorded since server start, successes and errors alike.
        error_count: Total errors recorded since server start.
        last_duration_ms: Wall-clock milliseconds the most recent run took, or None.
    """

    model_config = ConfigDict(frozen=True)

    tick_count: int = 0
    error_count: int = 0
    last_duration_ms: float | None = None


def read_engine_status(client: httpx.Client) -> dict[str, EngineStatusSnapshot]:
    """Read every tick-registered engine's live status from GET /v1/clock/state.

    Free liveness and timing for all 46 engines, independent of whether any of
    them has a registered EngineProbe — the plain snapshot the API already emits.

    Args:
        client: Authenticated httpx.Client with base_url preset.
    Returns:
        Mapping from engine name to its EngineStatusSnapshot. Empty if the route
        call fails or the response carries no engine_status.
    """
    resp = client.get("/v1/clock/state")
    if resp.status_code != 200:
        return {}
    status = resp.json().get("data", {}).get("engine_status", {})
    if not isinstance(status, dict):
        return {}
    return {
        name: EngineStatusSnapshot.model_validate(record)
        for name, record in status.items()
        if isinstance(record, dict)
    }


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ProbeResult(BaseModel):
    """Aggregated result of k probe repetitions for one engine.

    Mirrors sequence_runner.SequenceResult's shape (scenario_id -> engine_name)
    but kept as its own model rather than reused directly, so a probe run is
    never structurally interchangeable with a promoted-scenario run by accident.

    Attributes:
        engine_name: Canonical engine key this probe measures.
        k: Number of repetitions requested.
        repetitions: One RepetitionRecord per run, in order.
        stat: Fidelity-gated SequenceStat aggregated over invariant pass/fail,
            with metrics_summary holding the per-key mean across repetitions.
    """

    model_config = ConfigDict(frozen=True)

    engine_name: str
    k: int
    repetitions: tuple[RepetitionRecord, ...]
    stat: SequenceStat


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_invariants(client: httpx.Client, probe: EngineProbe) -> str | None:
    """Run every declared invariant in order; return the first failing name.

    Args:
        client: Authenticated httpx.Client with base_url preset.
        probe: The EngineProbe whose invariants to check.
    Returns:
        The name of the first invariant that returned False, or None if all pass.
    """
    name: str
    for name, check in probe.invariants.items():
        if not check(client):
            return name
    return None


def _merge_status_metrics(
    metrics: dict[str, float], status: EngineStatusSnapshot | None
) -> dict[str, float]:
    """Fold an engine's free status fields into a probe's own metrics dict.

    The probe's own measure() keys always win on collision — these three are a
    floor, not an override, of what a probe already chose to report.

    Args:
        metrics: The probe's own measure() output for this repetition.
        status: This probe's engine_name entry from read_engine_status, or None
            if the engine has never run or the status call failed.
    Returns:
        A new dict — metrics is not mutated in place.
    """
    merged = dict(metrics)
    if status is not None:
        merged.setdefault("tick_count", float(status.tick_count))
        merged.setdefault("error_count", float(status.error_count))
        if status.last_duration_ms is not None:
            merged.setdefault("duration_ms", float(status.last_duration_ms))
    return merged


def _execute_probe_cycle(
    client: httpx.Client, probe: EngineProbe, ticks: int
) -> tuple[bool, dict[str, float], str | None]:
    """Run one setup->drive->measure->invariants cycle; let the caller time and catch it.

    Args:
        client: Authenticated httpx.Client with base_url preset.
        probe: The EngineProbe to run.
        ticks: Ticks to advance, forwarded to probe.drive().
    Returns:
        (passed, metrics, error) — error names the first failing invariant, or
        None when every declared invariant held.
    """
    probe.setup(client)
    probe.drive(client, ticks)
    metrics = _merge_status_metrics(
        dict(probe.measure(client)), read_engine_status(client).get(probe.engine_name)
    )
    failed_invariant = _check_invariants(client, probe)
    if failed_invariant is not None:
        return False, metrics, f"invariant failed: {failed_invariant}"
    return True, metrics, None


def _run_one_probe_repetition(
    repetition: int,
    client: httpx.Client,
    probe: EngineProbe,
    ticks: int,
    reset_receipt: ResetReceipt,
) -> RepetitionRecord:
    """Time one probe cycle and record its outcome.

    A step that raises is recorded as a failed repetition (error captured,
    metrics empty) rather than aborting the run — the same record-not-abort
    contract evals/sequence_runner.py's _run_one uses for the promoted scenarios.

    Args:
        repetition: Zero-based index of this run within the k-set.
        client: Authenticated httpx.Client with base_url preset.
        probe: The EngineProbe to run.
        ticks: Ticks to advance, forwarded to probe.drive().
        reset_receipt: Evidence of what the preceding reset cleared and left surviving.
    Returns:
        RepetitionRecord with outcome, timing, reset receipt, metrics, and any error.
    """
    t0 = time.monotonic()
    try:
        passed, metrics, error = _execute_probe_cycle(client, probe, ticks)
    except Exception as exc:  # intentional: record-not-abort contract
        passed, metrics, error = False, {}, str(exc)
    duration_ms = int((time.monotonic() - t0) * _MS_PER_S)
    return RepetitionRecord(
        repetition=repetition,
        passed=passed,
        duration_ms=duration_ms,
        reset_receipt=reset_receipt,
        error=error,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _run_k_repetitions(
    client: httpx.Client, probe: EngineProbe, k: int, ticks: int, reset: ResetFn
) -> list[RepetitionRecord]:
    """Run k reset->probe cycles, once each, in order."""
    records: list[RepetitionRecord] = []
    for i in range(k):
        reset_receipt = reset()
        records.append(_run_one_probe_repetition(i, client, probe, ticks, reset_receipt))
    return records


def _build_probe_result(engine_name: str, k: int, records: list[RepetitionRecord]) -> ProbeResult:
    """Aggregate a probe's k RepetitionRecords into a fidelity-gated ProbeResult."""
    passes = sum(1 for r in records if r.passed)
    stat = sequence_stat(
        engine_name,
        passes,
        tuple(r.reset_receipt for r in records),
        tuple(r.metrics for r in records),
    )
    return ProbeResult(engine_name=engine_name, k=k, repetitions=tuple(records), stat=stat)


def run_probe(
    client: httpx.Client,
    probe: EngineProbe,
    k: int,
    ticks: int = _DEFAULT_TICKS,
    reset_fn: ResetFn | None = None,
) -> ProbeResult:
    """Run one EngineProbe k times: reset, setup, drive, measure, check invariants.

    The reset is called exactly k times — once before each repetition — and
    never after the last one, matching sequence_runner.run_sequence's discipline.

    Args:
        client: Authenticated httpx.Client with base_url preset.
        probe: The EngineProbe to run.
        k: Number of repetitions to run (must be >= 1).
        ticks: Ticks to advance per repetition, forwarded to probe.drive().
        reset_fn: World-reset callable; defaults to sequence_reset.make_reset_fn.
    Returns:
        ProbeResult with one RepetitionRecord per run and a fidelity-gated stat.
    Raises:
        ValueError: When k < 1.
    """
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    reset = reset_fn if reset_fn is not None else make_reset_fn(client, base_url="")
    records = _run_k_repetitions(client, probe, k, ticks, reset)
    return _build_probe_result(probe.engine_name, k, records)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _format_status_line(name: str, status: EngineStatusSnapshot) -> str:
    """Render one engine's free liveness/timing line."""
    duration = f"{status.last_duration_ms:.1f}ms" if status.last_duration_ms is not None else "n/a"
    return f"{name}: tick_count={status.tick_count} error_count={status.error_count} last_duration={duration}"


def _format_probe_line(result: ProbeResult) -> str:
    """Render one probe's fidelity-gated rate + metrics line."""
    stat = result.stat
    header = f"{result.engine_name} reaches {stat.passes}/{stat.k} (k={stat.k}, {stat.fidelity})"
    if stat.metrics_summary:
        parts = ", ".join(f"{k}={v:.3f}" for k, v in sorted(stat.metrics_summary.items()))
        return f"{header} metrics: {parts}"
    return header


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the `probe` verb's argument parser."""
    parser = argparse.ArgumentParser(
        description="Per-engine probe measurement (measurement-remediation Phase 3/4)."
    )
    parser.add_argument("--base-url", default=_DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--k", type=int, default=_DEFAULT_K)
    parser.add_argument("--ticks", type=int, default=_DEFAULT_TICKS)
    return parser


def _print_report(status: dict[str, EngineStatusSnapshot], results: list[ProbeResult]) -> None:
    """Print the free engine-status snapshot, then any registered probes' results."""
    print("ENGINE STATUS (free liveness/timing, all tick-registered engines):")
    for name in sorted(status):
        print(f"  {_format_status_line(name, status[name])}")

    if results:
        print("\nPROBE RESULTS:")
        for result in results:
            print(f"  {_format_probe_line(result)}")
    else:
        print("\nNo probes registered (PROBE_FACTORIES is empty).")


def main(argv: list[str] | None = None) -> int:
    """Advance the clock once, run every registered probe k times, and print the report.

    Always reports the free per-engine liveness/timing snapshot for every tick-
    registered engine, whether or not a probe exists for it — PROBE_FACTORIES
    covers gossip, events, memory, quest, dialogue, and the 6 ported legacy
    scenarios (measurement-remediation Phase 4, DEC-271); every other tick-
    registered engine still gets the free ENGINE STATUS line alone.
    """
    args = _build_arg_parser().parse_args(argv)

    with httpx.Client(
        base_url=args.base_url,
        headers={"Authorization": f"Bearer {args.api_key}"},
        timeout=180.0,
    ) as client:
        client.post(
            "/v1/clock/advance",
            json={"delta_ticks": args.ticks, "game_time_seconds": args.ticks},
        )
        status = read_engine_status(client)
        results = [
            run_probe(client, factory(client), args.k, args.ticks)
            for factory in PROBE_FACTORIES.values()
        ]

    _print_report(status, results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
