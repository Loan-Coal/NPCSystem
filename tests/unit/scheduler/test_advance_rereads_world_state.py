"""
test_advance_rereads_world_state.py - Guards the frozen-clock bug (L13-09, SEV-08).

A batched advance must re-read world state on every tick so engines observe
changing time_of_day, not a snapshot frozen from before the loop started.

Does NOT: open Neo4j, call an LLM, or perform real graph I/O.
Dependencies injected: mock for get_world_state; AsyncMock session.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.scheduler.game_clock import GameClock
from npc_engine.scheduler.tick_scheduler import TickScheduler
from npc_engine.world.world_state import WorldState


class _CapturingRoutineEngine:
    """RoutineTickEngine stub that records each time_of_day it is called with."""

    def __init__(self) -> None:
        self.seen_time_of_days: list[str] = []

    async def run_tick(self, *, time_of_day: str, tick_id: int) -> dict[str, Any]:
        self.seen_time_of_days.append(time_of_day)
        return {"moved": 1}


class _NoopIntervalHandler:
    """Minimal gossip/event stub — interval is set to 100 so it never fires."""

    async def run_tick(self, *, tick_id: int, **kwargs: Any) -> dict[str, Any]:
        return {}


@pytest.mark.asyncio
async def test_routine_engine_sees_changing_time_of_day_across_ticks() -> None:
    """2-tick advance across evening→night must deliver distinct time_of_day per tick.

    Failing today: advance() reads world_state once before the loop, so both ticks
    receive the same frozen snapshot ('evening').  After the fix the read moves inside
    the loop, and tick 2 sees the updated value ('night').
    """
    routine = _CapturingRoutineEngine()
    scheduler = TickScheduler(
        clock=GameClock(mode="game_driven"),
        gossip_handler=_NoopIntervalHandler(),
        event_handler=_NoopIntervalHandler(),
        gossip_interval=100,
        event_interval=100,
        routine_engine=routine,
    )

    # Three values: one for the pre-loop fallback read, then one per tick.
    world_states = [
        WorldState(time_of_day="evening"),  # pre-loop read (zero-delta fallback)
        WorldState(time_of_day="evening"),  # tick 1 in-loop re-read
        WorldState(time_of_day="night"),    # tick 2 in-loop re-read
    ]

    with patch(
        "npc_engine.scheduler.tick_scheduler.get_world_state",
        new=AsyncMock(side_effect=world_states),
    ):
        await scheduler.advance(session=AsyncMock(), tick_delta=2, time_delta_seconds=2)

    # Frozen-clock bug: both ticks see "evening".
    # Fixed behaviour: tick 1 → "evening", tick 2 → "night".
    assert routine.seen_time_of_days == ["evening", "night"], (
        f"got {routine.seen_time_of_days!r} — "
        "tick loop is still using a frozen world_state snapshot (L13-09)"
    )
