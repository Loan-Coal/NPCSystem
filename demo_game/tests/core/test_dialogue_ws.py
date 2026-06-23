"""
Module: test_dialogue_ws
Layer: demo_game (tests)
Purpose: Unit tests for demo_game.dialogue_ws — WebSocket dialogue streaming client.
         All network I/O is mocked via unittest.mock.
Dependencies: demo_game.dialogue_ws, unittest.mock, queue
Used by: make test-demo
"""

from __future__ import annotations

import json
import queue
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from demo_game.dialogue_ws import dialogue_ws_worker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ws_mock(messages: list[dict]):
    """Return a context-manager-compatible WS mock that replays messages."""
    ws = MagicMock()
    ws.recv.side_effect = [json.dumps(m) for m in messages]
    ws.send = MagicMock()
    return ws


@contextmanager
def _patch_ws(ws_mock):
    """Patch websockets.sync.client.connect to yield ws_mock."""
    with patch("demo_game.dialogue_ws.websockets.sync.client.connect") as mock_connect:
        mock_connect.return_value.__enter__ = MagicMock(return_value=ws_mock)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        yield mock_connect


_PAYLOAD = {"player_id": "player_demo", "npc_id": "mira_innkeeper", "player_message": "Hello"}
_WS_URL = "ws://localhost:8000"
_API_KEY = "test-key"


# ---------------------------------------------------------------------------
# Token streaming
# ---------------------------------------------------------------------------


class TestDialogueWsTokens:
    def test_single_token_and_done(self) -> None:
        """Single token followed by done → one token event then done event."""
        ws = _make_ws_mock([
            {"type": "token", "data": "Hello "},
            {"type": "done", "data": {"degradation_level": "full", "emotion": "happy",
                                      "relation_deltas": {}, "action": {"type": "speak"},
                                      "facial_expression": {"type": "smile"}}},
        ])
        result_q: queue.Queue = queue.Queue()
        with _patch_ws(ws):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q)

        items = list(result_q.queue)
        assert items[0] == ("token", "Hello ")
        assert items[1][0] == "done"
        assert items[1][1]["degradation_level"] == "full"

    def test_multiple_tokens_accumulated(self) -> None:
        """Three token messages appear as three separate token events."""
        ws = _make_ws_mock([
            {"type": "token", "data": "Hello "},
            {"type": "token", "data": "there "},
            {"type": "token", "data": "friend."},
            {"type": "done", "data": {}},
        ])
        result_q: queue.Queue = queue.Queue()
        with _patch_ws(ws):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q)

        items = list(result_q.queue)
        token_items = [i for i in items if i[0] == "token"]
        assert len(token_items) == 3
        assert token_items[0] == ("token", "Hello ")
        assert token_items[1] == ("token", "there ")
        assert token_items[2] == ("token", "friend.")

    def test_done_metadata_forwarded(self) -> None:
        """done metadata dict is forwarded intact into the result queue."""
        metadata = {
            "degradation_level": "graph_only",
            "emotion": "neutral",
            "relation_deltas": {"trust": 3, "fear": 0, "affection": 0},
            "action": {"type": "speak", "target_id": None, "parameters": {}},
            "facial_expression": {"type": "neutral", "intensity": 0},
        }
        ws = _make_ws_mock([{"type": "done", "data": metadata}])
        result_q: queue.Queue = queue.Queue()
        with _patch_ws(ws):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q)

        item = result_q.get_nowait()
        assert item[0] == "done"
        # audio_bytes is always injected (None when absent from server data)
        assert item[1]["degradation_level"] == "graph_only"
        assert item[1]["emotion"] == "neutral"
        assert item[1]["relation_deltas"] == {"trust": 3, "fear": 0, "affection": 0}
        assert item[1].get("audio_bytes") is None

    def test_done_with_no_data_field(self) -> None:
        """done message without a data field yields metadata with audio_bytes=None."""
        ws = _make_ws_mock([{"type": "done"}])
        result_q: queue.Queue = queue.Queue()
        with _patch_ws(ws):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q)

        item = result_q.get_nowait()
        assert item[0] == "done"
        assert item[1] == {"audio_bytes": None}

    def test_send_payload_serialised_as_json(self) -> None:
        """Payload dict is serialised and sent as a JSON string."""
        ws = _make_ws_mock([{"type": "done", "data": {}}])
        result_q: queue.Queue = queue.Queue()
        with _patch_ws(ws) as mock_connect:
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q)

        ws.send.assert_called_once()
        sent = json.loads(ws.send.call_args[0][0])
        assert sent["player_id"] == _PAYLOAD["player_id"]
        assert sent["npc_id"] == _PAYLOAD["npc_id"]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestDialogueWsErrors:
    def test_server_error_message_yields_error_tuple(self) -> None:
        """A server {"type": "error"} message yields an ("error", exc) tuple."""
        ws = _make_ws_mock([{"type": "error", "data": "internal_error"}])
        result_q: queue.Queue = queue.Queue()
        with _patch_ws(ws):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q)

        item = result_q.get_nowait()
        assert item[0] == "error"
        assert "internal_error" in str(item[1])

    def test_connection_failure_yields_error_tuple(self) -> None:
        """A connection-level exception yields an ("error", exc) tuple."""
        result_q: queue.Queue = queue.Queue()
        with patch("demo_game.dialogue_ws.websockets.sync.client.connect",
                   side_effect=ConnectionRefusedError("refused")):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q)

        item = result_q.get_nowait()
        assert item[0] == "error"
        assert isinstance(item[1], ConnectionRefusedError)

    def test_authorization_header_sent(self) -> None:
        """Bearer token is sent in the Authorization upgrade header."""
        ws = _make_ws_mock([{"type": "done", "data": {}}])
        result_q: queue.Queue = queue.Queue()
        with _patch_ws(ws) as mock_connect:
            dialogue_ws_worker(_WS_URL, "my-secret-key", _PAYLOAD, result_q)

        _, kwargs = mock_connect.call_args
        headers = dict(kwargs.get("additional_headers", {}))
        assert headers.get("Authorization") == "Bearer my-secret-key"

    def test_uri_constructed_from_ws_url(self) -> None:
        """URI passed to connect appends the correct WS path."""
        ws = _make_ws_mock([{"type": "done", "data": {}}])
        result_q: queue.Queue = queue.Queue()
        with _patch_ws(ws) as mock_connect:
            dialogue_ws_worker("ws://engine:9000", _API_KEY, _PAYLOAD, result_q)

        positional = mock_connect.call_args[0]
        assert positional[0] == "ws://engine:9000/v1/ws/dialogue"

    def test_stream_stops_after_error_message(self) -> None:
        """No further items are pushed after a server error message."""
        ws = _make_ws_mock([
            {"type": "token", "data": "hi"},
            {"type": "error", "data": "boom"},
            # This extra message should never be read.
            {"type": "token", "data": "ignored"},
        ])
        result_q: queue.Queue = queue.Queue()
        with _patch_ws(ws):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q)

        items = list(result_q.queue)
        assert items[-1][0] == "error"
        # Only two items: one token and one error.
        assert len(items) == 2


# ---------------------------------------------------------------------------
# Audio bytes decoding
# ---------------------------------------------------------------------------


class TestDialogueWsAudio:
    def test_done_with_audio_bytes_b64_decoded_to_bytes(self) -> None:
        """audio_bytes_b64 in done data is decoded to raw bytes in metadata."""
        import base64
        wav_bytes = b"RIFF\x00\x00\x00\x00WAVEfmt "
        metadata = {
            "degradation_level": "full",
            "emotion": None,
            "relation_deltas": {},
            "action": {"type": "speak"},
            "facial_expression": {"type": "neutral"},
            "audio_bytes_b64": base64.b64encode(wav_bytes).decode(),
        }
        ws = _make_ws_mock([{"type": "done", "data": metadata}])
        result_q: queue.Queue = queue.Queue()
        with _patch_ws(ws):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q)

        item = result_q.get_nowait()
        assert item[0] == "done"
        assert item[1].get("audio_bytes") == wav_bytes

    def test_done_without_audio_bytes_b64_gives_none(self) -> None:
        """When audio_bytes_b64 is absent from done data, audio_bytes is None in metadata."""
        metadata = {"degradation_level": "full", "emotion": None}
        ws = _make_ws_mock([{"type": "done", "data": metadata}])
        result_q: queue.Queue = queue.Queue()
        with _patch_ws(ws):
            dialogue_ws_worker(_WS_URL, _API_KEY, _PAYLOAD, result_q)

        item = result_q.get_nowait()
        assert item[0] == "done"
        assert item[1].get("audio_bytes") is None
