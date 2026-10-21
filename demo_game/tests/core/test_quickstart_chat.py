"""
Module: test_quickstart_chat
Layer: demo_game (tests)
Purpose: Unit tests for the chat_repl REPL in demo_game.quickstart.
         Stubs dialogue_ws_worker and asserts two stdin lines produce two
         worker calls and two printed npc_response lines.
Dependencies: demo_game.quickstart, unittest.mock, io
Used by: make test-demo
"""

from __future__ import annotations

import io
import queue
from unittest.mock import patch

from demo_game.quickstart import chat_repl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_ws_worker(ws_url: str, api_key: str, payload: dict, result_q: queue.Queue) -> None:
    """Fake dialogue_ws_worker that pushes a canned done event without network I/O."""
    result_q.put(("done", {
        "emotion": "neutral",
        "relation_deltas": {"trust": 0},
        "degradation_level": "full",
        "action": {},
        "facial_expression": {},
        "audio_bytes": None,
    }))


# ---------------------------------------------------------------------------
# Chat REPL tests
# ---------------------------------------------------------------------------


class TestChatRepl:
    def test_two_lines_produce_two_sends_and_two_replies(self, capsys) -> None:
        """Two stdin lines each produce one worker call and one printed npc_response."""
        stdin_mock = io.StringIO("Hello there\nHow are you\n")
        with patch("demo_game.quickstart.dialogue_ws_worker", side_effect=_fake_ws_worker) as mock_worker:
            with patch("sys.stdin", stdin_mock):
                chat_repl("ws://localhost:8000", "test-key", "npc_001")

        assert mock_worker.call_count == 2
        out = capsys.readouterr().out
        assert out.count("npc_response:") == 2

    def test_payload_carries_npc_id(self, capsys) -> None:
        """The payload forwarded to the worker uses the npc_id passed to chat_repl."""
        stdin_mock = io.StringIO("Hi\n")
        with patch("demo_game.quickstart.dialogue_ws_worker", side_effect=_fake_ws_worker) as mock_worker:
            with patch("sys.stdin", stdin_mock):
                chat_repl("ws://localhost:8000", "key", "aria_baker")

        _, _key, payload, _q = mock_worker.call_args[0]
        assert payload["npc_id"] == "aria_baker"
        assert payload["player_message"] == "Hi"

    def test_empty_lines_are_skipped(self, capsys) -> None:
        """Blank lines do not produce a worker call."""
        stdin_mock = io.StringIO("Hi\n\n\nBye\n")
        with patch("demo_game.quickstart.dialogue_ws_worker", side_effect=_fake_ws_worker) as mock_worker:
            with patch("sys.stdin", stdin_mock):
                chat_repl("ws://localhost:8000", "key", "npc_001")

        assert mock_worker.call_count == 2

    def test_emotion_and_relation_deltas_printed(self, capsys) -> None:
        """emotion and relation_deltas from the done event appear in output."""
        def _worker_with_data(ws_url, api_key, payload, result_q):
            result_q.put(("done", {
                "emotion": "happy",
                "relation_deltas": {"trust": 5},
                "degradation_level": "full",
                "audio_bytes": None,
            }))

        stdin_mock = io.StringIO("Hello\n")
        with patch("demo_game.quickstart.dialogue_ws_worker", side_effect=_worker_with_data):
            with patch("sys.stdin", stdin_mock):
                chat_repl("ws://localhost:8000", "key", "npc_001")

        out = capsys.readouterr().out
        assert "happy" in out
        assert "trust" in out
