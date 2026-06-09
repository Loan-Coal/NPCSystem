"""
Tests for ProactiveDialogueTick adapter (EXP-10 slice-2).

All tests are fully mocked — no DB, no LLM connections.

Covers:
  - trigger fires → generate_line called
  - no trigger → generate_line NOT called
  - pairs capped at MAX_PROACTIVE_CHECKS_PER_TICK
  - no collocated pairs → returns {"proactive_lines": []}
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.proactive_dialogue.models import ProactiveLine, ProactiveTrigger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trigger(npc_id: str = "npc_1", player_id: str = "player") -> ProactiveTrigger:
    return ProactiveTrigger(
        npc_id=npc_id,
        player_id=player_id,
        tick_id=10,
        reason="unshared_memory",
        memory_id="m1",
        memory_content="Something important happened.",
        memory_vividness=80,
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
    result = await adapter.run_tick(session=MagicMock(), tick_id=10)

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
    result = await adapter.run_tick(session=MagicMock(), tick_id=5)

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
    await adapter.run_tick(session=MagicMock(), tick_id=1)

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
    result = await adapter.run_tick(session=MagicMock(), tick_id=3)

    engine.check_trigger.assert_not_awaited()
    assert result == {"proactive_lines": []}


# ---------------------------------------------------------------------------
# test_tick_adapter_multiple_pairs_with_trigger
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_adapter_multiple_pairs_with_trigger() -> None:
    """Multiple pairs, first triggers → both checked, one line in output."""
    from npc_engine.engines.proactive_dialogue.proactive_tick_adapter import ProactiveDialogueTick

    trigger_1 = _make_trigger(npc_id="npc_1")
    line_1 = _make_line(npc_id="npc_1")

    call_count = 0

    async def _check_trigger(session: Any, *, npc_id: str, player_id: str, tick_id: int) -> ProactiveTrigger | None:
        nonlocal call_count
        call_count += 1
        if npc_id == "npc_1":
            return trigger_1
        return None

    engine = MagicMock()
    engine.check_trigger = AsyncMock(side_effect=_check_trigger)
    engine.generate_line = AsyncMock(return_value=line_1)

    location_reader = _make_location_reader([("npc_1", "player"), ("npc_2", "player")])

    adapter = ProactiveDialogueTick(engine=engine, location_reader=location_reader)
    result = await adapter.run_tick(session=MagicMock(), tick_id=10)

    assert engine.check_trigger.await_count == 2
    assert engine.generate_line.await_count == 1
    assert len(result["proactive_lines"]) == 1
    assert result["proactive_lines"][0]["npc_id"] == "npc_1"
