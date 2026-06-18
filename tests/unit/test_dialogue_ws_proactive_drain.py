"""
Unit tests for the drain_proactive_lines helper in api.routes.dialogue_ws (F1.2).

These tests are hermetic — no Neo4j, no WebSocket server, no LLM.
They drive drain_proactive_lines with a fake WebSocket (records send_json calls)
and a real ProactiveQueue pre-loaded with lines to verify end-to-end delivery.

Covers:
  - All pre-loaded lines are flushed via to_ws_message() → send_json.
  - Queue is empty after drain.
  - Recipient with no lines results in zero sends.
  - Multiple rounds: enqueue between drains accumulates correctly.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.proactive_dialogue.models import ProactiveLine
from npc_engine.engines.proactive_dialogue.proactive_queue import ProactiveQueue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_line(npc_id: str = "npc_1", tick: int = 1) -> ProactiveLine:
    return ProactiveLine(
        npc_id=npc_id,
        content=f"Hello from {npc_id} at tick {tick}.",
        reason="unshared_memory",
        tick=tick,
    )


class _FakeWebSocket:
    """Minimal WebSocket stub that records send_json calls."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.send_json = AsyncMock(side_effect=self._record)

    async def _record(self, payload: dict[str, Any]) -> None:
        self.sent.append(payload)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDrainProactiveLines:
    """drain_proactive_lines flushes buffered lines to the WebSocket."""

    @pytest.mark.asyncio
    async def test_lines_pushed_and_queue_emptied(self) -> None:
        """Pre-loaded lines are all sent via to_ws_message(); queue is empty after."""
        from npc_engine.api.routes.dialogue_ws import drain_proactive_lines

        queue = ProactiveQueue()
        line_a = _make_line("npc_1", tick=10)
        line_b = _make_line("npc_2", tick=11)
        await queue.enqueue("player_x", line_a)
        await queue.enqueue("player_x", line_b)

        ws = _FakeWebSocket()
        sent_count = await drain_proactive_lines(ws, queue, "player_x")

        assert sent_count == 2
        assert len(ws.sent) == 2
        assert ws.sent[0] == line_a.to_ws_message()
        assert ws.sent[1] == line_b.to_ws_message()
        # Queue must be empty afterwards.
        assert queue.drain("player_x") == []

    @pytest.mark.asyncio
    async def test_empty_queue_sends_nothing(self) -> None:
        """drain_proactive_lines returns 0 and does nothing when queue is empty."""
        from npc_engine.api.routes.dialogue_ws import drain_proactive_lines

        queue = ProactiveQueue()
        ws = _FakeWebSocket()

        sent_count = await drain_proactive_lines(ws, queue, "player_no_lines")

        assert sent_count == 0
        ws.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_isolates_per_recipient(self) -> None:
        """Lines for a different recipient are not sent to this recipient."""
        from npc_engine.api.routes.dialogue_ws import drain_proactive_lines

        queue = ProactiveQueue()
        line_for_other = _make_line("npc_3", tick=5)
        await queue.enqueue("player_other", line_for_other)

        ws = _FakeWebSocket()
        sent_count = await drain_proactive_lines(ws, queue, "player_target")

        assert sent_count == 0
        # Other recipient's line must still be in the queue.
        assert len(queue.drain("player_other")) == 1

    @pytest.mark.asyncio
    async def test_multiple_drain_rounds(self) -> None:
        """Enqueueing between drain calls accumulates correctly."""
        from npc_engine.api.routes.dialogue_ws import drain_proactive_lines

        queue = ProactiveQueue()
        ws = _FakeWebSocket()

        await queue.enqueue("p1", _make_line(tick=1))
        round_1 = await drain_proactive_lines(ws, queue, "p1")

        await queue.enqueue("p1", _make_line(tick=2))
        await queue.enqueue("p1", _make_line(tick=3))
        round_2 = await drain_proactive_lines(ws, queue, "p1")

        assert round_1 == 1
        assert round_2 == 2
        assert len(ws.sent) == 3

    @pytest.mark.asyncio
    async def test_ws_message_type_is_proactive_line(self) -> None:
        """Each sent payload has type 'proactive_line' per DEC-073 wire format."""
        from npc_engine.api.routes.dialogue_ws import drain_proactive_lines

        queue = ProactiveQueue()
        await queue.enqueue("p1", _make_line("npc_1", tick=7))
        ws = _FakeWebSocket()
        await drain_proactive_lines(ws, queue, "p1")

        assert ws.sent[0]["type"] == "proactive_line"
