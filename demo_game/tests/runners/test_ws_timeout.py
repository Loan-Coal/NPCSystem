"""
Module: test_ws_timeout
Layer: demo_game (tests)
Purpose: ISSUE-347 regression — a WebSocket recv that times out must put an error
         event onto the result queue rather than breaking silently and hanging the
         caller forever.
Dependencies: demo_game.dialogue_ws, unittest.mock, queue
Used by: make test-demo
"""

from __future__ import annotations

import queue
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from demo_game.dialogue_ws import dialogue_ws_worker

_PAYLOAD = {"player_id": "player_demo", "npc_id": "mira_innkeeper", "player_message": "Hi"}
_WS_URL = "ws://localhost:8000"
_API_KEY = "test-key"


@contextmanager
def _patch_ws(ws_mock: MagicMock):
    """Patch websockets.sync.client.connect to yield ws_mock."""
    with patch("demo_game.dialogue_ws.websockets.sync.client.connect") as mock_connect:
        mock_connect.return_value.__enter__ = MagicMock(return_value=ws_mock)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        yield mock_connect


class TestWsRecvTimeout:
    def test_timeout_puts_error_on_queue(self) -> None:
        """When recv raises TimeoutError the worker puts an ('error', TimeoutError) tuple on the queue."""
        ws = MagicMock()
        ws.recv.side_effect = TimeoutError("stubbed timeout")
        ws.send = MagicMock()

        result_q: queue.Queue = queue.Queue()
        with _patch_ws(ws):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q)

        assert not result_q.empty(), "queue must not be empty after a recv timeout"
        item = result_q.get_nowait()
        assert item[0] == "error"
        assert isinstance(item[1], TimeoutError)

    def test_timeout_does_not_hang_caller(self) -> None:
        """result_q.get_nowait() must succeed — worker must not exit without queuing an event."""
        ws = MagicMock()
        ws.recv.side_effect = TimeoutError("never answers")
        ws.send = MagicMock()

        result_q: queue.Queue = queue.Queue()
        with _patch_ws(ws):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q)

        # If this raises queue.Empty, the bug is still present.
        try:
            result_q.get_nowait()
        except queue.Empty:
            pytest.fail("queue is empty — worker exited on timeout without queuing an error event")
