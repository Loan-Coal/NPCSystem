"""
Tests for engines.proactive_dialogue.proactive_queue — ProactiveQueue.

Covers:
- test_enqueue_then_drain_returns_lines
- test_drain_empty_returns_empty
- test_drain_is_per_recipient
"""

from __future__ import annotations

import asyncio

import pytest

from src.npc_engine.engines.proactive_dialogue.models import ProactiveLine
from src.npc_engine.engines.proactive_dialogue.proactive_queue import ProactiveQueue


def _make_line(npc_id: str = "npc_a", tick: int = 1) -> ProactiveLine:
    return ProactiveLine(
        npc_id=npc_id,
        content="Hello traveller.",
        reason="unshared_memory",
        tick=tick,
    )


# ---------------------------------------------------------------------------
# RED-first tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_then_drain_returns_lines() -> None:
    """Lines enqueued for a recipient are returned by drain."""
    queue = ProactiveQueue()
    line = _make_line()
    await queue.enqueue("player_1", line)

    result = queue.drain("player_1")

    assert result == [line]


@pytest.mark.asyncio
async def test_drain_empty_returns_empty() -> None:
    """Draining a recipient with no lines returns an empty list."""
    queue = ProactiveQueue()

    result = queue.drain("player_unknown")

    assert result == []


@pytest.mark.asyncio
async def test_drain_is_per_recipient() -> None:
    """Lines for recipient A are not returned when draining recipient B."""
    queue = ProactiveQueue()
    line_a = _make_line(npc_id="npc_a", tick=1)
    line_b = _make_line(npc_id="npc_b", tick=2)

    await queue.enqueue("player_a", line_a)
    await queue.enqueue("player_b", line_b)

    result_a = queue.drain("player_a")
    result_b = queue.drain("player_b")

    assert result_a == [line_a]
    assert result_b == [line_b]


@pytest.mark.asyncio
async def test_drain_clears_buffer() -> None:
    """After drain, the buffer for the recipient is empty."""
    queue = ProactiveQueue()
    await queue.enqueue("player_1", _make_line())

    queue.drain("player_1")
    second_drain = queue.drain("player_1")

    assert second_drain == []


@pytest.mark.asyncio
async def test_enqueue_multiple_lines_ordered() -> None:
    """Multiple lines for the same recipient come back in enqueue order."""
    queue = ProactiveQueue()
    line1 = _make_line(tick=1)
    line2 = _make_line(tick=2)
    line3 = _make_line(tick=3)

    await queue.enqueue("player_1", line1)
    await queue.enqueue("player_1", line2)
    await queue.enqueue("player_1", line3)

    result = queue.drain("player_1")

    assert result == [line1, line2, line3]
