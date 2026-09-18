"""
test_skip_llm_engines_covers_quest_triggers.py - Assert quest triggers are gated by skip_llm_engines.

Finding L13-05, SEV-02. RED anchor for T7.1 Step 1.

Does NOT: open Neo4j, call an LLM, or perform real graph I/O.
Dependencies mocked: get_world_state, persist_clock_state, is_tick_done, mark_tick_done.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.scheduler.game_clock import GameClock
from npc_engine.scheduler.tick_scheduler import TickScheduler
from npc_engine.world.world_state import WorldState

_WORLD = WorldState()


class _CountingEngine:
    """TickEngine stub that counts run_tick() invocations."""

    def __init__(self) -> None:
        """Initialise call counter to zero."""
        self.call_count: int = 0

    async def run_tick(self, *, tick_id: int) -> dict[str, Any]:
        """Increment the call counter and return an empty result."""
        self.call_count += 1
        return {}


@pytest.mark.asyncio
async def test_skip_llm_engines_covers_quest_triggers() -> None:
    """With skip_llm_engines=True, all three quest trigger engines must make zero calls.

    On the current tree this fails because the quest triggers run unconditionally in
    _ordered_tick_engines() without any skip_llm_engines gate. The chapter engine is
    already gated; this test proves quest triggers must be too (L13-05, SEV-02).

    63 of the 84 worst-case per-tick LLM calls originate from quest triggers, so
    shedding removes only 25% without this fix.
    """
    event_quest = _CountingEngine()
    need_quest = _CountingEngine()
    world_state_quest = _CountingEngine()

    scheduler = TickScheduler(
        clock=GameClock(mode="game_driven"),
        gossip_handler=AsyncMock(**{"run_tick.return_value": {}}),
        event_handler=AsyncMock(**{"run_tick.return_value": {}}),
        gossip_interval=1,
        event_interval=1,
        event_quest_trigger=event_quest,
        need_quest_trigger=need_quest,
        world_state_quest_trigger=world_state_quest,
        distributed_lease_enabled=False,
    )

    with (
        patch(
            "npc_engine.scheduler.tick_scheduler.get_world_state",
            new=AsyncMock(return_value=_WORLD),
        ),
        patch(
            "npc_engine.scheduler.tick_scheduler.persist_clock_state",
            new=AsyncMock(),
        ),
        patch(
            "npc_engine.scheduler.tick_scheduler.is_tick_done",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "npc_engine.scheduler.tick_scheduler.mark_tick_done",
            new=AsyncMock(),
        ),
    ):
        await scheduler.advance(
            session=AsyncMock(),
            tick_delta=1,
            time_delta_seconds=60,
            skip_llm_engines=True,
        )

    assert event_quest.call_count == 0, (
        f"event_quest ran {event_quest.call_count} time(s) with skip_llm_engines=True; "
        "quest triggers must be gated by skip_llm_engines (L13-05, SEV-02)"
    )
    assert need_quest.call_count == 0, (
        f"need_quest ran {need_quest.call_count} time(s) with skip_llm_engines=True"
    )
    assert world_state_quest.call_count == 0, (
        f"world_state_quest ran {world_state_quest.call_count} time(s) with skip_llm_engines=True"
    )


@pytest.mark.asyncio
async def test_quest_triggers_run_when_llm_not_skipped() -> None:
    """Without skip_llm_engines, quest triggers must run normally."""
    event_quest = _CountingEngine()
    need_quest = _CountingEngine()
    world_state_quest = _CountingEngine()

    scheduler = TickScheduler(
        clock=GameClock(mode="game_driven"),
        gossip_handler=AsyncMock(**{"run_tick.return_value": {}}),
        event_handler=AsyncMock(**{"run_tick.return_value": {}}),
        gossip_interval=1,
        event_interval=1,
        event_quest_trigger=event_quest,
        need_quest_trigger=need_quest,
        world_state_quest_trigger=world_state_quest,
        distributed_lease_enabled=False,
    )

    with (
        patch(
            "npc_engine.scheduler.tick_scheduler.get_world_state",
            new=AsyncMock(return_value=_WORLD),
        ),
        patch(
            "npc_engine.scheduler.tick_scheduler.persist_clock_state",
            new=AsyncMock(),
        ),
        patch(
            "npc_engine.scheduler.tick_scheduler.is_tick_done",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "npc_engine.scheduler.tick_scheduler.mark_tick_done",
            new=AsyncMock(),
        ),
    ):
        await scheduler.advance(
            session=AsyncMock(),
            tick_delta=1,
            time_delta_seconds=60,
            skip_llm_engines=False,
        )

    assert event_quest.call_count == 1
    assert need_quest.call_count == 1
    assert world_state_quest.call_count == 1
