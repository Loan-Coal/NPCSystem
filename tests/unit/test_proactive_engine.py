"""
test_proactive_engine.py - Unit tests for ProactiveDialogueEngine.

Tests trigger detection on high-vividness unshared memory + idle co-located
player, and that generate_line calls the LLM exactly once with correct prompt args.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.proactive_dialogue.models import ProactiveLine, ProactiveTrigger
from npc_engine.engines.proactive_dialogue.proactive_engine import (
    HIGH_VIVIDNESS_THRESHOLD,
    MIN_IDLE_TICKS,
    ProactiveDialogueEngine,
)


# ---------------------------------------------------------------------------
# Fake session and services
# ---------------------------------------------------------------------------


class _FakeMemory:
    """Minimal fake memory record returned from memory service."""

    def __init__(
        self,
        memory_id: str,
        content: str,
        vividness: int,
        shared: bool = False,
    ) -> None:
        self.memory_id = memory_id
        self.content = content
        self.vividness = vividness
        self.shared = shared


class _FakeMemoryService:
    """Stub memory service returning preset memories."""

    def __init__(self, memories: list[_FakeMemory]) -> None:
        self._memories = memories

    async def get_unshared_memories(
        self, *, npc_id: str, k: int = 5
    ) -> list[dict[str, Any]]:
        """Return memories as dicts matching the graph layer contract."""
        return [
            {
                "memory_id": m.memory_id,
                "content": m.content,
                "vividness": m.vividness,
                "shared": m.shared,
            }
            for m in self._memories
        ]


class _FakeLocationService:
    """Stub location service controlling NPC / player co-location checks."""

    def __init__(self, co_located: bool, idle_ticks: int) -> None:
        self._co_located = co_located
        self._idle_ticks = idle_ticks

    async def get_player_idle_ticks(
        self, *, npc_id: str, player_id: str, tick_id: int
    ) -> int:
        """Return how many ticks the player has been idle at the NPC's location."""
        return self._idle_ticks if self._co_located else 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine(
    memories: list[_FakeMemory],
    co_located: bool = True,
    idle_ticks: int = MIN_IDLE_TICKS,
) -> tuple[ProactiveDialogueEngine, AsyncMock]:
    """Build a ProactiveDialogueEngine with stub deps; return engine + llm mock."""
    llm_client = AsyncMock()
    llm_client.generate = AsyncMock(return_value="Hello traveller, I must tell you something.")

    memory_service = _FakeMemoryService(memories)
    location_service = _FakeLocationService(co_located=co_located, idle_ticks=idle_ticks)

    engine = ProactiveDialogueEngine(
        llm_client=llm_client,
        memory_service=memory_service,
        location_service=location_service,
    )
    return engine, llm_client


# ---------------------------------------------------------------------------
# check_trigger tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trigger_fires_on_high_vividness_unshared_memory() -> None:
    """Trigger returns a ProactiveTrigger when high-vividness unshared memory exists and player is idle."""
    memories = [
        _FakeMemory("m1", "I saw the northern army march through the valley.", vividness=HIGH_VIVIDNESS_THRESHOLD + 5, shared=False),
    ]
    engine, _ = _make_engine(memories, co_located=True, idle_ticks=MIN_IDLE_TICKS)

    trigger = await engine.check_trigger(
        npc_id="captain_sorn",
        player_id="player_1",
        tick_id=100,
    )

    assert trigger is not None
    assert isinstance(trigger, ProactiveTrigger)
    assert trigger.npc_id == "captain_sorn"
    assert trigger.player_id == "player_1"
    assert trigger.reason == "unshared_memory"
    assert trigger.memory_content == "I saw the northern army march through the valley."


@pytest.mark.asyncio
async def test_trigger_does_not_fire_when_memory_below_threshold() -> None:
    """Trigger returns None when all memories are below vividness threshold."""
    memories = [
        _FakeMemory("m1", "I saw a squirrel.", vividness=HIGH_VIVIDNESS_THRESHOLD - 10, shared=False),
    ]
    engine, _ = _make_engine(memories, co_located=True, idle_ticks=MIN_IDLE_TICKS)

    trigger = await engine.check_trigger(
        npc_id="mira_innkeeper",
        player_id="player_1",
        tick_id=101,
    )

    assert trigger is None


@pytest.mark.asyncio
async def test_trigger_does_not_fire_when_player_not_co_located() -> None:
    """Trigger returns None when player is not co-located with the NPC."""
    memories = [
        _FakeMemory("m1", "A significant event.", vividness=HIGH_VIVIDNESS_THRESHOLD + 5, shared=False),
    ]
    engine, _ = _make_engine(memories, co_located=False, idle_ticks=0)

    trigger = await engine.check_trigger(
        npc_id="captain_sorn",
        player_id="player_1",
        tick_id=102,
    )

    assert trigger is None


@pytest.mark.asyncio
async def test_trigger_does_not_fire_when_player_idle_ticks_insufficient() -> None:
    """Trigger returns None when player has not been idle long enough."""
    memories = [
        _FakeMemory("m1", "A significant event.", vividness=HIGH_VIVIDNESS_THRESHOLD + 5, shared=False),
    ]
    # Co-located but fewer idle ticks than required
    engine, _ = _make_engine(memories, co_located=True, idle_ticks=MIN_IDLE_TICKS - 1)

    trigger = await engine.check_trigger(
        npc_id="captain_sorn",
        player_id="player_1",
        tick_id=103,
    )

    assert trigger is None


@pytest.mark.asyncio
async def test_trigger_selects_highest_vividness_memory() -> None:
    """Trigger picks the highest-vividness qualifying memory when multiple exist."""
    memories = [
        _FakeMemory("m1", "Minor memory.", vividness=HIGH_VIVIDNESS_THRESHOLD + 2, shared=False),
        _FakeMemory("m2", "Major memory.", vividness=HIGH_VIVIDNESS_THRESHOLD + 20, shared=False),
        _FakeMemory("m3", "Another minor.", vividness=HIGH_VIVIDNESS_THRESHOLD + 5, shared=False),
    ]
    engine, _ = _make_engine(memories, co_located=True, idle_ticks=MIN_IDLE_TICKS)

    trigger = await engine.check_trigger(
        npc_id="aldric_merchant",
        player_id="player_1",
        tick_id=104,
    )

    assert trigger is not None
    assert trigger.memory_content == "Major memory."


@pytest.mark.asyncio
async def test_trigger_does_not_fire_when_no_memories() -> None:
    """Trigger returns None when the NPC has no unshared memories at all."""
    engine, _ = _make_engine(memories=[], co_located=True, idle_ticks=MIN_IDLE_TICKS)

    trigger = await engine.check_trigger(
        npc_id="old_henryk",
        player_id="player_1",
        tick_id=105,
    )

    assert trigger is None


# ---------------------------------------------------------------------------
# generate_line tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_line_calls_llm_exactly_once() -> None:
    """generate_line calls the LLM exactly once and returns a ProactiveLine."""
    memories = [
        _FakeMemory("m1", "I witnessed something important.", vividness=HIGH_VIVIDNESS_THRESHOLD + 10, shared=False),
    ]
    engine, llm_client = _make_engine(memories)

    trigger = ProactiveTrigger(
        npc_id="captain_sorn",
        player_id="player_1",
        tick_id=100,
        reason="unshared_memory",
        memory_id="m1",
        memory_content="I witnessed something important.",
        memory_vividness=HIGH_VIVIDNESS_THRESHOLD + 10,
    )

    line = await engine.generate_line(trigger=trigger)

    llm_client.generate.assert_called_once()
    assert isinstance(line, ProactiveLine)
    assert line.npc_id == "captain_sorn"
    assert line.reason == "unshared_memory"
    assert line.tick == 100
    assert isinstance(line.content, str)
    assert len(line.content) > 0


@pytest.mark.asyncio
async def test_generate_line_prompt_includes_memory_content() -> None:
    """generate_line passes the memory content into the prompt call."""
    memories: list[_FakeMemory] = []
    engine, llm_client = _make_engine(memories)

    trigger = ProactiveTrigger(
        npc_id="mira_innkeeper",
        player_id="player_2",
        tick_id=200,
        reason="unshared_memory",
        memory_id="m99",
        memory_content="The merchant was poisoned at dawn.",
        memory_vividness=90,
    )

    await engine.generate_line(trigger=trigger)

    call_kwargs = llm_client.generate.call_args
    # The prompt (positional or keyword) should contain the memory content
    prompt_arg = call_kwargs[1].get("prompt") or call_kwargs[0][0]
    assert "The merchant was poisoned at dawn." in prompt_arg


@pytest.mark.asyncio
async def test_generate_line_returns_proactive_line_with_correct_shape() -> None:
    """ProactiveLine from generate_line has all required WS-envelope fields (DEC-073)."""
    memories: list[_FakeMemory] = []
    engine, _ = _make_engine(memories)

    trigger = ProactiveTrigger(
        npc_id="lira_fence",
        player_id="player_3",
        tick_id=300,
        reason="unshared_memory",
        memory_id="m77",
        memory_content="I know who stole the dagger.",
        memory_vividness=85,
    )

    line = await engine.generate_line(trigger=trigger)

    # Validate WS message shape from DEC-073
    ws_payload = line.to_ws_message()
    assert ws_payload["type"] == "proactive_line"
    assert ws_payload["npc_id"] == "lira_fence"
    assert ws_payload["reason"] == "unshared_memory"
    assert ws_payload["tick"] == 300
    assert isinstance(ws_payload["content"], str)
