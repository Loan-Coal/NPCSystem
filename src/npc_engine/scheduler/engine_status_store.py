"""
Module: engine_status_store
Layer: engines
Purpose: In-memory per-engine status tracking: last-run tick id, last error, and working set size.
Does NOT: persist data to Neo4j or perform I/O of any kind.
Dependencies injected: none (standalone value object)
Dependencies: pydantic (BaseModel, ConfigDict), utils.metrics (gauge emission)
Used by: tick_scheduler (writes), api.routes.clock (reads via TickScheduler.engine_status)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from npc_engine.utils.metrics import set_gauge_metric

_ENGINE_ERROR_COUNT_METRIC = "engine_error_count"
_ENGINE_LAST_ERROR_TICK_METRIC = "engine_last_error_tick"
_ENGINE_WORKING_SET_SIZE_METRIC = "engine_working_set_size"


class EngineStatusRecord(BaseModel):
    """Immutable snapshot of one engine's last-run status.

    Args:
        engine_name: Canonical engine key (e.g. "gossip", "event").
        last_tick_id: Tick ID of the last successful run_tick call, or None.
        last_error: Error message from the most recent failure, or None.
        last_error_tick: Tick ID on which the last error occurred, or None.
        error_count: Total number of errors recorded since server start.
        last_duration_ms: Wall-clock milliseconds the most recent run took, or None
            if this engine last ran before timing existed.
        tick_count: Total runs recorded since server start, successes and errors alike.
        working_set_size: Sum of work-count fields from the engine's last result dict,
            or None when not reported. Zero means the engine ran but processed nothing.
    """

    engine_name: str
    last_tick_id: int | None = None
    last_error: str | None = None
    last_error_tick: int | None = None
    error_count: int = 0
    last_duration_ms: float | None = None
    tick_count: int = 0
    working_set_size: int | None = None

    model_config = ConfigDict(frozen=True)


class EngineStatusStore:
    """In-memory store tracking per-engine last-run tick and last error.

    All mutations happen inside TickScheduler's asyncio.Lock, so no
    additional locking is needed here. Reads from API routes are
    eventually consistent — acceptable for observability data.

    Side-effects: record_success and record_error push gauges to the process-level
    MetricsRegistry so the values are visible in GET /v1/admin/system/metrics.
    """

    def __init__(self) -> None:
        """Initialise with an empty status map."""
        self._records: dict[str, EngineStatusRecord] = {}

    def _emit_gauges(
        self,
        engine_name: str,
        error_count: int,
        *,
        last_error_tick: int | None = None,
        working_set_size: int | None = None,
    ) -> None:
        """Emit per-engine observability gauges to the process-level MetricsRegistry.

        Args:
            engine_name: Canonical engine key used as the ``engine`` label.
            error_count: Current total error count to push as a gauge.
            last_error_tick: Tick ID of the most recent error, or None to skip.
            working_set_size: Sum of work-count fields, or None to skip.
        """
        labels = {"engine": engine_name}
        set_gauge_metric(_ENGINE_ERROR_COUNT_METRIC, float(error_count), labels=labels)
        if last_error_tick is not None:
            set_gauge_metric(_ENGINE_LAST_ERROR_TICK_METRIC, float(last_error_tick), labels=labels)
        if working_set_size is not None:
            set_gauge_metric(_ENGINE_WORKING_SET_SIZE_METRIC, float(working_set_size), labels=labels)

    def record_success(
        self,
        engine_name: str,
        tick_id: int,
        *,
        duration_ms: float | None = None,
        working_set_size: int | None = None,
    ) -> None:
        """Record a successful engine tick.

        Updates last_tick_id and increments tick_count; preserves last_error and
        error_count unchanged. Emits engine_error_count and (when provided)
        engine_working_set_size gauges to the process-level MetricsRegistry.

        Args:
            engine_name: Canonical engine key.
            tick_id: Tick ID that completed successfully.
            duration_ms: Wall-clock milliseconds the run took, or None when untimed.
            working_set_size: Sum of work-count values in the engine's result dict,
                or None when the engine did not report them.
        """
        existing = self._records.get(engine_name)
        new_error_count = existing.error_count if existing else 0
        new_working_set_size = (
            working_set_size if working_set_size is not None
            else (existing.working_set_size if existing else None)
        )
        self._records[engine_name] = EngineStatusRecord(
            engine_name=engine_name,
            last_tick_id=tick_id,
            last_error=existing.last_error if existing else None,
            last_error_tick=existing.last_error_tick if existing else None,
            error_count=new_error_count,
            last_duration_ms=duration_ms,
            tick_count=(existing.tick_count if existing else 0) + 1,
            working_set_size=new_working_set_size,
        )
        self._emit_gauges(engine_name, new_error_count, working_set_size=working_set_size)

    def record_error(
        self, engine_name: str, tick_id: int, error: str, *, duration_ms: float | None = None
    ) -> None:
        """Record an engine tick failure.

        Updates last_error and last_error_tick; preserves last_tick_id and working_set_size.
        Increments error_count and tick_count. Emits engine_error_count and
        engine_last_error_tick gauges to the process-level MetricsRegistry.

        Args:
            engine_name: Canonical engine key.
            tick_id: Tick ID on which the error occurred.
            error: String representation of the exception.
            duration_ms: Wall-clock milliseconds the run took, or None when untimed.
        """
        existing = self._records.get(engine_name)
        new_error_count = (existing.error_count if existing else 0) + 1
        self._records[engine_name] = EngineStatusRecord(
            engine_name=engine_name,
            last_tick_id=existing.last_tick_id if existing else None,
            last_error=error,
            last_error_tick=tick_id,
            error_count=new_error_count,
            last_duration_ms=duration_ms,
            tick_count=(existing.tick_count if existing else 0) + 1,
            working_set_size=existing.working_set_size if existing else None,
        )
        self._emit_gauges(engine_name, new_error_count, last_error_tick=tick_id)

    def get(self, engine_name: str) -> EngineStatusRecord | None:
        """Return the status record for one engine, or None if never run.

        Args:
            engine_name: Canonical engine key.
        Returns:
            EngineStatusRecord or None.
        """
        return self._records.get(engine_name)

    def get_all(self) -> dict[str, EngineStatusRecord]:
        """Return a shallow copy of all engine status records.

        Returns:
            Dict mapping engine name to its EngineStatusRecord.
        """
        return dict(self._records)
