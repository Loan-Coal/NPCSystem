"""
Module: tick_autopilot
Layer: engines
Purpose: Background task that autonomously advances the world clock at a fixed wall-clock interval.
Does NOT: implement per-engine tick logic or modify game state directly.
Dependencies injected: _GraphDbProtocol (graph_db), TickScheduler (tick_scheduler), TickBudgetGuard (budget_guard).
Used by: api.main (lifespan background task).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Protocol

from npc_engine.scheduler.tick_budget_guard import TickBudgetGuard

if TYPE_CHECKING:
    from npc_engine.scheduler.tick_scheduler import TickScheduler


LOGGER = logging.getLogger(__name__)


class _GraphDbProtocol(Protocol):
    """Structural protocol — any object with a get_session() context manager."""

    def get_session(self):
        """Return an async context manager yielding an AsyncSession."""


class TickAutopilot:
    """Drives the world clock forward autonomously at a wall-clock cadence.

    Calls ``TickScheduler.advance()`` once per ``interval_seconds``, advancing
    by one game tick and ``game_seconds_per_tick`` in-game seconds each time.
    When a ``TickBudgetGuard`` is provided, LLM engines are skipped for ticks
    that would exceed the per-minute LLM call ceiling; a ``tick_budget_exceeded``
    log entry is emitted for each skipped tick.

    Exceptions from individual advance calls are logged and swallowed so a
    transient Neo4j or engine failure cannot kill the loop.

    The class acquires a fresh Neo4j session for each advance call; it does not
    hold an open session between iterations.
    """

    def __init__(
        self,
        graph_db: _GraphDbProtocol,
        tick_scheduler: TickScheduler,
        interval_seconds: int,
        game_seconds_per_tick: int,
        budget_guard: TickBudgetGuard | None = None,
    ) -> None:
        """Initialise the autopilot.

        Args:
            graph_db: Provider of Neo4j async sessions via ``get_session()``.
            tick_scheduler: Scheduler whose ``advance()`` is called each iteration.
            interval_seconds: Wall-clock seconds between advances (minimum 1).
            game_seconds_per_tick: In-game seconds advanced per tick (minimum 0).
            budget_guard: Optional sliding-window LLM call ceiling enforcer.
                When None, LLM engines always run (no budget limiting).
        """
        self._graph_db = graph_db
        self._tick_scheduler = tick_scheduler
        self._interval_seconds = max(1, interval_seconds)
        self._game_seconds_per_tick = max(0, game_seconds_per_tick)
        self._budget_guard = budget_guard

    async def advance_once(self) -> dict:
        """Advance the world clock by one tick using a fresh session.

        When a budget_guard is configured and the LLM budget is exhausted,
        LLM engines (chapter, memory_consolidation) are skipped and
        ``tick_budget_exceeded`` is logged.

        Returns:
            The result dict from TickScheduler.advance().
        Raises:
            Any exception from the underlying scheduler or database.
        """
        skip_llm = False
        if self._budget_guard is not None:
            skip_llm = self._budget_guard.should_skip_llm()
            if skip_llm:
                LOGGER.warning(
                    "tick_budget_exceeded",
                    extra={"remaining": 0, "max_per_minute": self._budget_guard._max_per_minute},
                )

        async with self._graph_db.get_session() as session:
            result = await self._tick_scheduler.advance(
                session=session,
                tick_delta=1,
                time_delta_seconds=self._game_seconds_per_tick,
                skip_llm_engines=skip_llm,
            )

        if self._budget_guard is not None and not skip_llm:
            self._budget_guard.record_llm_tick()

        return result

    async def run_forever(self) -> None:
        """Run the autopilot loop until task cancellation.

        Advances one tick per iteration, then sleeps ``interval_seconds``.
        Non-cancellation exceptions are logged and the loop continues.

        Raises:
            asyncio.CancelledError: Propagated on task cancellation.
        """
        while True:
            try:
                result = await self.advance_once()
                clock = result.get("clock", {})
                LOGGER.info(
                    "autopilot_tick_advanced",
                    extra={
                        "tick_id": clock.get("tick_id"),
                        "gossip_count": len(result.get("gossip", [])),
                        "event_count": len(result.get("event", [])),
                    },
                )
            except asyncio.CancelledError:
                LOGGER.info("tick_autopilot_cancelled")
                raise
            except Exception:
                LOGGER.exception("tick_autopilot_advance_failed")
            await asyncio.sleep(self._interval_seconds)
