"""
Tests for ProactiveDialogueTick adapter (F1.2 — router + queue wiring).

All tests are fully mocked — no DB, no LLM connections.

Covers:
  - trigger fires → generate_line called, line in output
  - no trigger → generate_line NOT called, empty output
  - pairs capped at MAX_PROACTIVE_CHECKS_PER_TICK
  - no collocated pairs → returns {"proactive_lines": []}
  - multiple pairs trigger → EXACTLY ONE winner (highest priority) enqueued
  - without injected queue → no enqueue, still returns line
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.proactive_dialogue.models import ProactiveLine, ProactiveTrigger
from npc_engine.engines.proactive_dialogue.proactive_queue import ProactiveQueue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trigger(
    npc_id: str = "npc_1",
    player_id: str = "player",
    memory_vividness: int = 80,
) -> ProactiveTrigger:
    return ProactiveTrigger(
        npc_id=npc_id,
        player_id=player_id,
        tick_id=10,
        reason="unshared_memory",
        memory_id="m1",
        memory_content="Something important happened.",
        memory_vividness=memory_vividness,
    )


def _make_line(npc_id: str = "npc_1") -> ProactiveLine:
    return ProactiveLine(
        npc_id=npc_id,
        content="Hello there, traveller.",
        reason="unshared_memory",
        tick=10,
    )


def _make_engine(
    trigger: ProactiveTrigger | None,
    line: ProactiveLine | None = None,
) -> MagicMock:
    """Mock ProactiveDialogueEngine with controllable check_trigger/generate_line."""
    engine = MagicMock()
    engine.check_trigger = AsyncMock(return_value=trigger)
    engine.generate_line = AsyncMock(return_value=line or (
        _make_line() if trigger is not None else None
    ))
    return engine


def _make_location_reader(pairs: list[tuple[str, str]]) -> MagicMock:
    """Mock PlayerLocationReader whose get_collocated_pairs returns ``pairs``."""
    reader = MagicMock()
    reader.get_collocated_pairs = AsyncMock(return_value=pairs)
    return reader


# ---------------------------------------------------------------------------
# test_tick_adapter_fires_on_trigger
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_adapter_fires_on_trigger() -> None:
    """When check_trigger returns a trigger, generate_line is called once."""
    from npc_engine.engines.proactive_dialogue.proactive_tick_adapter import ProactiveDialogueTick

    trigger = _make_trigger()
    line = _make_line()
    engine = _make_engine(trigger, line)
    location_reader = _make_location_reader([("npc_1", "player")])

    adapter = ProactiveDialogueTick(engine=engine, location_reader=location_reader)
    result = await adapter.run_tick(tick_id=10)

    engine.check_trigger.assert_awaited_once()
    engine.generate_line.assert_awaited_once()
    assert "proactive_lines" in result
    assert len(result["proactive_lines"]) == 1


# ---------------------------------------------------------------------------
# test_tick_adapter_skips_on_no_trigger
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_adapter_skips_on_no_trigger() -> None:
    """When check_trigger returns None, generate_line is NOT called."""
    from npc_engine.engines.proactive_dialogue.proactive_tick_adapter import ProactiveDialogueTick

    engine = _make_engine(trigger=None)
    location_reader = _make_location_reader([("npc_1", "player")])

    adapter = ProactiveDialogueTick(engine=engine, location_reader=location_reader)
    result = await adapter.run_tick(tick_id=5)

    engine.check_trigger.assert_awaited_once()
    engine.generate_line.assert_not_awaited()
    assert result == {"proactive_lines": []}


# ---------------------------------------------------------------------------
# test_tick_adapter_caps_pairs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_adapter_caps_pairs() -> None:
    """When >MAX_PROACTIVE_CHECKS_PER_TICK pairs exist, only first MAX are checked."""
    from npc_engine.engines.proactive_dialogue.proactive_tick_adapter import (
        MAX_PROACTIVE_CHECKS_PER_TICK,
        ProactiveDialogueTick,
    )

    # Create more pairs than the cap
    over_cap = MAX_PROACTIVE_CHECKS_PER_TICK + 5
    pairs = [(f"npc_{i}", "player") for i in range(over_cap)]

    engine = _make_engine(trigger=None)
    location_reader = _make_location_reader(pairs)

    adapter = ProactiveDialogueTick(engine=engine, location_reader=location_reader)
    await adapter.run_tick(tick_id=1)

    assert engine.check_trigger.await_count == MAX_PROACTIVE_CHECKS_PER_TICK, (
        f"Expected {MAX_PROACTIVE_CHECKS_PER_TICK} checks, "
        f"got {engine.check_trigger.await_count}"
    )


# ---------------------------------------------------------------------------
# test_tick_adapter_returns_empty_no_pairs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_adapter_returns_empty_no_pairs() -> None:
    """No collocated pairs → run_tick returns {'proactive_lines': []}."""
    from npc_engine.engines.proactive_dialogue.proactive_tick_adapter import ProactiveDialogueTick

    engine = _make_engine(trigger=None)
    location_reader = _make_location_reader([])

    adapter = ProactiveDialogueTick(engine=engine, location_reader=location_reader)
    result = await adapter.run_tick(tick_id=3)

    engine.check_trigger.assert_not_awaited()
    assert result == {"proactive_lines": []}


# ---------------------------------------------------------------------------
# test_tick_adapter_multiple_pairs_with_trigger
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_adapter_multiple_pairs_with_trigger() -> None:
    """Multiple pairs, first triggers → both checked, exactly ONE winner in output."""
    from npc_engine.engines.proactive_dialogue.proactive_tick_adapter import ProactiveDialogueTick

    trigger_1 = _make_trigger(npc_id="npc_1", memory_vividness=80)
    line_1 = _make_line(npc_id="npc_1")

    async def _check_trigger(*, npc_id: str, player_id: str, tick_id: int) -> ProactiveTrigger | None:
        if npc_id == "npc_1":
            return trigger_1
        return None

    engine = MagicMock()
    engine.check_trigger = AsyncMock(side_effect=_check_trigger)
    engine.generate_line = AsyncMock(return_value=line_1)

    location_reader = _make_location_reader([("npc_1", "player"), ("npc_2", "player")])

    adapter = ProactiveDialogueTick(engine=engine, location_reader=location_reader)
    result = await adapter.run_tick(tick_id=10)

    assert engine.check_trigger.await_count == 2
    # Router picks the single winner — generate_line called exactly once.
    assert engine.generate_line.await_count == 1
    assert len(result["proactive_lines"]) == 1
    assert result["proactive_lines"][0]["npc_id"] == "npc_1"


# ---------------------------------------------------------------------------
# test_tick_adapter_enqueues_winner_to_queue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_adapter_enqueues_winner_to_queue() -> None:
    """When multiple pairs trigger, only the highest-priority winner is enqueued."""
    from npc_engine.engines.proactive_dialogue.proactive_tick_adapter import ProactiveDialogueTick

    # npc_2 has higher vividness → higher priority → should win routing.
    trigger_low = _make_trigger(npc_id="npc_1", player_id="player", memory_vividness=60)
    trigger_high = _make_trigger(npc_id="npc_2", player_id="player", memory_vividness=95)
    line_high = _make_line(npc_id="npc_2")

    async def _check_trigger(*, npc_id: str, player_id: str, tick_id: int) -> ProactiveTrigger | None:
        if npc_id == "npc_1":
            return trigger_low
        if npc_id == "npc_2":
            return trigger_high
        return None

    engine = MagicMock()
    engine.check_trigger = AsyncMock(side_effect=_check_trigger)
    engine.generate_line = AsyncMock(return_value=line_high)

    location_reader = _make_location_reader([("npc_1", "player"), ("npc_2", "player")])
    queue = ProactiveQueue()

    adapter = ProactiveDialogueTick(engine=engine, location_reader=location_reader, proactive_queue=queue)
    result = await adapter.run_tick(tick_id=10)

    # Exactly one line enqueued (the winner).
    drained = queue.drain("player")
    assert len(drained) == 1
    assert drained[0].npc_id == "npc_2"

    # Return value also reflects the single winner.
    assert len(result["proactive_lines"]) == 1
    assert result["proactive_lines"][0]["npc_id"] == "npc_2"


@pytest.mark.asyncio
async def test_tick_adapter_ignores_scheduler_session_kwarg() -> None:
    """The scheduler passes ``session=``; run_tick must accept and ignore it (SEV-24)."""
    from npc_engine.engines.proactive_dialogue.proactive_tick_adapter import ProactiveDialogueTick

    engine = _make_engine(trigger=None)
    location_reader = _make_location_reader([])

    adapter = ProactiveDialogueTick(engine=engine, location_reader=location_reader)
    result = await adapter.run_tick(tick_id=7)

    location_reader.get_collocated_pairs.assert_awaited_once_with()
    assert result == {"proactive_lines": []}


# ---------------------------------------------------------------------------
# ISSUE-094: need/event proactive trigger producers
# ---------------------------------------------------------------------------


def _make_intent_repo(
    unmet_needs: list[dict] | None = None,
    witnessed_events: list[dict] | None = None,
) -> MagicMock:
    """Mock IntentGraphPort with configurable need/event returns."""
    repo = MagicMock()
    repo.get_unmet_needs = AsyncMock(return_value=unmet_needs or [])
    repo.get_witnessed_events = AsyncMock(return_value=witnessed_events or [])
    return repo


@pytest.mark.asyncio
async def test_need_candidate_fires_when_no_memory_trigger() -> None:
    """ISSUE-094: unmet need produces a TriggerCandidate(source='need') that wins the router
    when no memory candidate exists and generates a proactive line."""
    from npc_engine.engines.proactive_dialogue.proactive_tick_adapter import ProactiveDialogueTick

    engine = _make_engine(trigger=None)
    line = _make_line()
    engine.generate_line = AsyncMock(return_value=line)

    location_reader = _make_location_reader([("npc_1", "player")])
    intent_repo = _make_intent_repo(
        unmet_needs=[{"id": "need_hunger", "intensity": 90, "label": "hunger"}]
    )

    adapter = ProactiveDialogueTick(
        engine=engine, location_reader=location_reader, intent_repo=intent_repo
    )
    result = await adapter.run_tick(tick_id=10)

    engine.generate_line.assert_awaited_once()
    assert len(result["proactive_lines"]) == 1


@pytest.mark.asyncio
async def test_event_candidate_fires_when_no_memory_trigger() -> None:
    """ISSUE-094: witnessed event produces a TriggerCandidate(source='event') that wins
    the router when no memory candidate exists and generates a proactive line."""
    from npc_engine.engines.proactive_dialogue.proactive_tick_adapter import ProactiveDialogueTick

    engine = _make_engine(trigger=None)
    line = _make_line()
    engine.generate_line = AsyncMock(return_value=line)

    location_reader = _make_location_reader([("npc_1", "player")])
    intent_repo = _make_intent_repo(
        witnessed_events=[{"id": "evt_fire", "severity": 80, "summary": "The market is on fire!"}]
    )

    adapter = ProactiveDialogueTick(
        engine=engine, location_reader=location_reader, intent_repo=intent_repo
    )
    result = await adapter.run_tick(tick_id=10)

    engine.generate_line.assert_awaited_once()
    assert len(result["proactive_lines"]) == 1


@pytest.mark.asyncio
async def test_high_priority_need_beats_low_vividness_memory() -> None:
    """ISSUE-094: a high-intensity need (priority=90) beats a low-vividness memory (priority=40)."""
    from npc_engine.engines.proactive_dialogue.proactive_tick_adapter import ProactiveDialogueTick

    low_vividness_trigger = _make_trigger(memory_vividness=40)
    line = _make_line()
    engine = _make_engine(trigger=low_vividness_trigger, line=line)

    location_reader = _make_location_reader([("npc_1", "player")])
    intent_repo = _make_intent_repo(
        unmet_needs=[{"id": "need_hunger", "intensity": 90, "label": "hunger"}]
    )

    adapter = ProactiveDialogueTick(
        engine=engine, location_reader=location_reader, intent_repo=intent_repo
    )
    result = await adapter.run_tick(tick_id=10)

    # Exactly one line generated (router picks the winner — the need candidate wins here).
    engine.generate_line.assert_awaited_once()
    assert len(result["proactive_lines"]) == 1


@pytest.mark.asyncio
async def test_tick_adapter_no_queue_still_returns_line() -> None:
    """Without an injected queue, winner is returned but nothing is enqueued."""
    from npc_engine.engines.proactive_dialogue.proactive_tick_adapter import ProactiveDialogueTick

    trigger = _make_trigger()
    line = _make_line()
    engine = _make_engine(trigger, line)
    location_reader = _make_location_reader([("npc_1", "player")])

    # No queue injected (backward-compatible default).
    adapter = ProactiveDialogueTick(engine=engine, location_reader=location_reader)
    result = await adapter.run_tick(tick_id=10)

    assert len(result["proactive_lines"]) == 1
    assert result["proactive_lines"][0]["npc_id"] == "npc_1"
