"""
base_engine.py - Declares the tick-engine contracts the scheduler calls against.
Layer: engines
Purpose: Declares the tick-engine contracts the scheduler calls against.

Does NOT: implement domain-specific engine behavior.

Dependencies injected: None.
"""
from __future__ import annotations

from typing import Any, Protocol

from npc_engine.world.time_utils import TimePoint


class TickEngine(Protocol):
    """Contract for an engine the scheduler drives with nothing but the tick id.

    Every ``TickScheduler`` engine slot uses this except the two the scheduler
    calls with different arguments — see ``RoutineTickEngine`` and
    ``ConsolidationTickEngine``. An implementation may declare further
    parameters only if every one of them has a default, because the scheduler
    never supplies them.
    """

    async def run_tick(self, *, tick_id: int) -> dict[str, Any]: ...


class RoutineTickEngine(Protocol):
    """Contract for the routine engine, which also needs the world's time of day."""

    async def run_tick(self, *, time_of_day: str, tick_id: int) -> dict[str, Any]: ...


class ConsolidationTickEngine(Protocol):
    """Contract for the memory-consolidation engine, driven by game time, not tick id."""

    async def run_tick(self, *, game_time: TimePoint) -> dict[str, Any]: ...
