"""
Module: test_ws_connection_slot_release
Layer: tests/unit/api
Purpose: Verify that the WebSocket connection slot is released when the client
         disconnects, so that MAX_WS_CONNECTIONS_PER_KEY sequential connections
         all succeed. Guards against the drain-loop slot leak (SEV-01, L9-01)
         where the idle loop never calls receive(), WebSocketDisconnect is never
         surfaced, and _release_ws_slot in the finally block is never reached.
Does NOT: test dialogue business logic, TTS, or auth rejection.
Dependencies: asyncio.create_task, unittest.mock.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect

from npc_engine.api.routes.dialogue.dialogue_ws import (
    MAX_WS_CONNECTIONS_PER_KEY,
    _active_ws_connections,
    dialogue_ws,
)

# Time (seconds) given to tasks to run through the drain loop and exit.
# Fixed code: each task completes in a handful of event-loop iterations well
# under this budget.  Buggy code: each task stalls in asyncio.sleep(0.5) and
# does NOT exit within this window — that is the observable difference.
_SETTLE_SECONDS: float = 0.15

_AUTH: str = "Bearer ws-slot-release-test"


def _make_ws() -> MagicMock:
    """Return a mock WebSocket that disconnects the moment receive() is awaited."""
    ws = MagicMock()
    ws.headers = {"Authorization": _AUTH}
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive = AsyncMock(side_effect=WebSocketDisconnect())
    return ws


class TestWsConnectionSlotRelease:
    """Slot is freed when the client disconnects so subsequent connections are not blocked."""

    async def test_sequential_connections_do_not_exhaust_slots(self) -> None:
        """MAX_WS_CONNECTIONS_PER_KEY+1 sequential connections are all accepted.

        Each mock client disconnects immediately after the first turn.  After
        the fix (asyncio.wait_for on websocket.receive), the drain loop detects
        the disconnect, _release_ws_slot runs, and the next connection may open.

        In the buggy code the drain loop only calls asyncio.sleep — receive() is
        never called, WebSocketDisconnect is never raised, and the finally block
        is never reached.  Five stalled tasks hold five slots; the 6th connection
        is rejected and the assertion below fails.
        """
        _active_ws_connections.clear()

        with (
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws"
                ".resolve_scope_from_authorization"
            ),
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws._run_first_turn",
                new=AsyncMock(return_value="player_1"),
            ),
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws.get_proactive_queue"
            ) as mq,
            patch(
                "npc_engine.api.routes.dialogue.dialogue_ws.get_settings"
            ),
        ):
            mq.return_value.drain.return_value = []

            # Start MAX connections, each with a client that disconnects immediately.
            tasks: list[asyncio.Task] = []
            for _ in range(MAX_WS_CONNECTIONS_PER_KEY):
                tasks.append(asyncio.create_task(dialogue_ws(_make_ws())))

            # Fixed code: every task completes (receive raises, finally releases slot).
            # Buggy code: every task stalls in asyncio.sleep(0.5) — slots remain held.
            await asyncio.sleep(_SETTLE_SECONDS)

            # Attempt the (MAX+1)th connection while the first MAX are still "open"
            # in buggy code.
            ws_last = _make_ws()
            tasks.append(asyncio.create_task(dialogue_ws(ws_last)))
            await asyncio.sleep(_SETTLE_SECONDS)

            # Tear down any tasks that are still running (buggy drain loop stalls).
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        assert ws_last.accept.called, (
            f"Connection {MAX_WS_CONNECTIONS_PER_KEY + 1} was not accepted — "
            "the WebSocket slot was not released by the preceding connections. "
            "The drain loop must call websocket.receive() (not asyncio.sleep only) "
            "so that a client-initiated close raises WebSocketDisconnect and the "
            "finally block reaches _release_ws_slot."
        )
