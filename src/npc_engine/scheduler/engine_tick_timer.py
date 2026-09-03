"""
Module: engine_tick_timer
Layer: engines
Purpose: Time one engine tick and record its outcome to the status store and the metrics registry.
         (scheduler/ is its own rank-5 layer in check_layers.py; the docstring audit's
         Layer vocabulary calls that 'engines', as every sibling here already does.)
Does NOT: run engines, decide whether an engine is due, touch Neo4j, or own the tick loop.
Dependencies: scheduler.engine_status_store, utils.metrics.
Dependencies injected: EngineStatusStore (optional) is passed to the constructor.
Used by: scheduler.tick_scheduler

Why this is a class and not two timers
-------------------------------------
TickScheduler runs engines down two different paths - `_run_engine_safe` for the simple
per-tick engines and `_run_distributed_interval` for the lease-held interval engines
(gossip and event). Those two already drifted apart once. Putting the stopwatch and the
metric emission in one place means a change to what "an engine tick cost" means lands on
both paths at once, while each path keeps its own rule about *when* a run counts as a
success - the distributed path only records one when it actually held the lease.
"""

from __future__ import annotations

from time import perf_counter

from npc_engine.scheduler.engine_status_store import EngineStatusStore
from npc_engine.utils.metrics import increment_metric, observe_metric

ENGINE_TICK_DURATION_MS_METRIC = "engine_tick_duration_ms"
ENGINE_TICKS_TOTAL_METRIC = "engine_ticks_total"

_SUCCESS_RESULT_LABEL = "success"
_ERROR_RESULT_LABEL = "error"
_MS_PER_SECOND = 1000.0


class EngineTickTimer:
    """Stopwatch for a single engine tick, started on construction.

    Construct one immediately before awaiting the engine, then call exactly one of
    ``record_success`` or ``record_error`` when the outcome is known. Both record the
    elapsed wall-clock time; neither raises if no status store was injected, because
    TickScheduler treats the store as optional and the metrics must not depend on it.

    Attributes:
        engine_name: Canonical engine key used as the metric label and store key.
        tick_id: Tick ID this run belongs to.
    """

    def __init__(
        self,
        *,
        engine_name: str,
        tick_id: int,
        status_store: EngineStatusStore | None,
    ) -> None:
        """Start the stopwatch for one engine tick.

        Args:
            engine_name: Canonical engine key (e.g. "gossip", "event").
            tick_id: Tick ID this run belongs to.
            status_store: Store to record the outcome in, or None to emit metrics only.
        """
        self.engine_name = engine_name
        self.tick_id = tick_id
        self._status_store = status_store
        self._started_at = perf_counter()

    def elapsed_ms(self) -> float:
        """Return milliseconds elapsed since construction."""
        return (perf_counter() - self._started_at) * _MS_PER_SECOND

    def record_success(self) -> None:
        """Record a successful engine tick with its duration."""
        duration_ms = self.elapsed_ms()
        if self._status_store is not None:
            self._status_store.record_success(
                self.engine_name, self.tick_id, duration_ms=duration_ms
            )
        self._emit(duration_ms=duration_ms, result=_SUCCESS_RESULT_LABEL)

    def record_error(self, error: str) -> None:
        """Record a failed engine tick with its duration.

        Args:
            error: String representation of the exception the engine raised.
        """
        duration_ms = self.elapsed_ms()
        if self._status_store is not None:
            self._status_store.record_error(
                self.engine_name, self.tick_id, error, duration_ms=duration_ms
            )
        self._emit(duration_ms=duration_ms, result=_ERROR_RESULT_LABEL)

    def _emit(self, *, duration_ms: float, result: str) -> None:
        observe_metric(
            metric=ENGINE_TICK_DURATION_MS_METRIC,
            value=duration_ms,
            labels={"engine": self.engine_name},
        )
        increment_metric(
            metric=ENGINE_TICKS_TOTAL_METRIC,
            amount=1.0,
            labels={"engine": self.engine_name, "result": result},
        )
