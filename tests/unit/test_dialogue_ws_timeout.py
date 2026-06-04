"""
Module: test_dialogue_ws_timeout
Layer: demo_game (tests)
Purpose: Regression tests for SEV-28 — ws.recv() timeout and clear_waiting watchdog.
         Verifies that a stalled or dead server connection never leaves _is_waiting True.
Dependencies: demo_game.dialogue_ws, demo_game.game_controller, unittest.mock, queue
Used by: make test (pytest tests/unit/)
"""

from __future__ import annotations

import queue
import threading
import time
from contextlib import contextmanager
from unittest.mock import MagicMock, call, patch

import pytest

from demo_game.dialogue_ws import dialogue_ws_worker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextmanager
def _patch_ws(ws_mock: MagicMock):
    """Patch websockets.sync.client.connect to yield ws_mock as the context value."""
    with patch("demo_game.dialogue_ws.websockets.sync.client.connect") as mock_connect:
        mock_connect.return_value.__enter__ = MagicMock(return_value=ws_mock)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        yield mock_connect


_PAYLOAD = {"player_id": "player_demo", "npc_id": "mira_innkeeper", "player_message": "Hello"}
_WS_URL = "ws://localhost:8000"
_API_KEY = "test-key"


# ---------------------------------------------------------------------------
# Timeout tests (SEV-28)
# ---------------------------------------------------------------------------


class TestDialogueWsTimeout:
    def test_timeout_error_exits_loop_and_calls_on_cleanup(self) -> None:
        """ws.recv() raising TimeoutError breaks the loop and on_cleanup is called."""
        ws = MagicMock()
        ws.recv.side_effect = TimeoutError("recv timed out")
        ws.send = MagicMock()

        result_q: queue.Queue = queue.Queue()
        cleanup_called = threading.Event()
        on_cleanup = MagicMock(side_effect=lambda: cleanup_called.set())

        with _patch_ws(ws):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q, on_cleanup)

        # on_cleanup must have been invoked exactly once
        on_cleanup.assert_called_once()
        # The queue should be empty — no error event pushed on a plain timeout
        assert result_q.empty()

    def test_is_waiting_cleared_after_timeout(self) -> None:
        """_is_waiting becomes False after a recv timeout via clear_waiting callback."""
        # Simulate GameController.clear_waiting behaviour directly
        is_waiting_state: list[bool] = [True]

        def clear_waiting() -> None:
            is_waiting_state[0] = False

        ws = MagicMock()
        ws.recv.side_effect = TimeoutError("recv timed out")
        ws.send = MagicMock()

        result_q: queue.Queue = queue.Queue()

        with _patch_ws(ws):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q, clear_waiting)

        assert is_waiting_state[0] is False, "_is_waiting must be False after timeout"

    def test_on_cleanup_called_on_normal_done(self) -> None:
        """on_cleanup is called even on a successful done frame (finally always runs)."""
        import json

        done_frame = json.dumps({"type": "done", "data": {"degradation_level": "full"}})
        ws = MagicMock()
        ws.recv.side_effect = [done_frame]
        ws.send = MagicMock()

        result_q: queue.Queue = queue.Queue()
        on_cleanup = MagicMock()

        with _patch_ws(ws):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q, on_cleanup)

        on_cleanup.assert_called_once()
        event = result_q.get_nowait()
        assert event[0] == "done"

    def test_on_cleanup_called_on_connection_error(self) -> None:
        """on_cleanup is called even when the connection itself fails."""
        result_q: queue.Queue = queue.Queue()
        on_cleanup = MagicMock()

        with patch(
            "demo_game.dialogue_ws.websockets.sync.client.connect",
            side_effect=ConnectionRefusedError("refused"),
        ):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q, on_cleanup)

        on_cleanup.assert_called_once()
        item = result_q.get_nowait()
        assert item[0] == "error"
        assert isinstance(item[1], ConnectionRefusedError)

    def test_no_on_cleanup_does_not_raise(self) -> None:
        """When on_cleanup is omitted (None), a timeout exits without raising."""
        import json

        ws = MagicMock()
        ws.recv.side_effect = TimeoutError("stall")
        ws.send = MagicMock()

        result_q: queue.Queue = queue.Queue()

        with _patch_ws(ws):
            # Must not raise
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q)

        assert result_q.empty()

    def test_timeout_passes_correct_timeout_arg_to_recv(self) -> None:
        """ws.recv() is called with timeout=NPC_DIALOGUE_TIMEOUT_S."""
        import json

        from demo_game.constants import NPC_DIALOGUE_TIMEOUT_S

        done_frame = json.dumps({"type": "done", "data": {}})
        ws = MagicMock()
        ws.recv.side_effect = [done_frame]
        ws.send = MagicMock()

        result_q: queue.Queue = queue.Queue()

        with _patch_ws(ws):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q)

        ws.recv.assert_called_with(timeout=NPC_DIALOGUE_TIMEOUT_S)
