"""
Module: engine_status_store
Layer: engines
Purpose: In-memory per-engine status tracking: last-run tick id and last error.
Does NOT: persist data to Neo4j or perform I/O of any kind.
Dependencies injected: none (standalone value object)
Dependencies: pydantic (BaseModel, ConfigDict)
Used by: tick_scheduler (writes), api.routes.clock (reads via TickScheduler.engine_status)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EngineStatusRecord(BaseModel):
    """Immutable snapshot of one engine's last-run status.

    Args:
        engine_name: Canonical engine key (e.g. "gossip", "event").
        last_tick_id: Tick ID of the last successful run_tick call, or None.
        last_error: Error message from the most recent failure, or None.
        last_error_tick: Tick ID on which the last error occurred, or None.
        error_count: Total number of errors recorded since server start.
    """

    engine_name: str
    last_tick_id: int | None = None
    last_error: str | None = None
    last_error_tick: int | None = None
    error_count: int = 0

    model_config = ConfigDict(frozen=True)


class EngineStatusStore:
    """In-memory store tracking per-engine last-run tick and last error.

    All mutations happen inside TickScheduler's asyncio.Lock, so no
    additional locking is needed here. Reads from API routes are
    eventually consistent — acceptable for observability data.
    """

    def __init__(self) -> None:
        """Initialise with an empty status map."""
        self._records: dict[str, EngineStatusRecord] = {}

    def record_success(self, engine_name: str, tick_id: int) -> None:
        """Record a successful engine tick.

        Updates last_tick_id; preserves last_error and error_count unchanged.

        Args:
            engine_name: Canonical engine key.
            tick_id: Tick ID that completed successfully.
        """
        existing = self._records.get(engine_name)
        self._records[engine_name] = EngineStatusRecord(
            engine_name=engine_name,
            last_tick_id=tick_id,
            last_error=existing.last_error if existing else None,
            last_error_tick=existing.last_error_tick if existing else None,
            error_count=existing.error_count if existing else 0,
        )

    def record_error(self, engine_name: str, tick_id: int, error: str) -> None:
        """Record an engine tick failure.

        Updates last_error and last_error_tick; preserves last_tick_id.
        Increments error_count.

        Args:
            engine_name: Canonical engine key.
            tick_id: Tick ID on which the error occurred.
            error: String representation of the exception.
        """
        existing = self._records.get(engine_name)
        self._records[engine_name] = EngineStatusRecord(
            engine_name=engine_name,
            last_tick_id=existing.last_tick_id if existing else None,
            last_error=error,
            last_error_tick=tick_id,
            error_count=(existing.error_count if existing else 0) + 1,
        )

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
