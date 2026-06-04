"""
Module: dialogue_ws
Layer: demo_game
Purpose: WebSocket dialogue streaming client for the demo game. Connects to the
         engine's /v1/ws/dialogue endpoint, forwards token chunks and completion
         metadata through a queue for the main thread to consume each frame.
Dependencies: websockets (via uvicorn[standard] transitive dep), json, queue,
              demo_game.constants
Used by: demo_game.game_controller
"""

from __future__ import annotations

import base64
import json
import logging
import queue
from collections.abc import Callable

import websockets.sync.client

from demo_game.constants import NPC_DIALOGUE_TIMEOUT_S

logger = logging.getLogger(__name__)

_WS_DIALOGUE_PATH = "/v1/ws/dialogue"


def dialogue_ws_worker(
    ws_url: str,
    api_key: str,
    payload: dict,
    result_q: queue.Queue,
    on_cleanup: Callable[[], None] | None = None,
) -> None:
    """Stream dialogue tokens via WebSocket and push typed events onto result_q.

    Connects synchronously (safe to call from a daemon thread). Sends the
    dialogue request JSON and consumes the server message stream.

    If the server closes the connection or stops sending frames for longer than
    ``NPC_DIALOGUE_TIMEOUT_S`` seconds, ``ws.recv()`` raises ``TimeoutError``;
    the loop exits cleanly and ``on_cleanup`` is called so the caller can release
    any waiting state (e.g. ``GameController.clear_waiting()``).

    ``on_cleanup`` is also called on normal completion and on connection errors,
    so callers must tolerate multiple invocations gracefully (idempotent).

    Events pushed onto result_q:
    - ``("token", chunk: str)`` — one word-chunk arrived; append to the log.
    - ``("done", metadata: dict)`` — stream complete; metadata has keys
      ``degradation_level``, ``emotion``, ``relation_deltas``, ``action``,
      ``facial_expression``.
    - ``("error", exc: Exception)`` — connection or protocol failure.

    Args:
        ws_url: WebSocket base URL, e.g. ``ws://localhost:8000``.
        api_key: Bearer token for authentication (sent in the Upgrade header).
        payload: Dialogue request body dict (player_id, npc_id, player_message, …).
        result_q: Queue to push typed event tuples onto.
        on_cleanup: Optional zero-argument callable invoked in the finally block.
            Use ``game_controller.clear_waiting`` to unlock the UI on any exit path.
    """
    uri = ws_url.rstrip("/") + _WS_DIALOGUE_PATH
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        with websockets.sync.client.connect(uri, additional_headers=headers) as ws:
            ws.send(json.dumps(payload))
            _recv_loop(ws, result_q)
    except Exception as exc:
        result_q.put(("error", exc))
    finally:
        if on_cleanup is not None:
            on_cleanup()


def _recv_loop(ws: websockets.sync.client.ClientConnection, result_q: queue.Queue) -> None:
    """Drain the WebSocket stream until done/error/timeout.

    Args:
        ws: Open synchronous WebSocket connection.
        result_q: Queue to push typed event tuples onto.
    """
    while True:
        try:
            raw = ws.recv(timeout=NPC_DIALOGUE_TIMEOUT_S)
        except TimeoutError:
            logger.warning(
                "ws_recv_timeout",
                extra={"timeout_s": NPC_DIALOGUE_TIMEOUT_S, "path": _WS_DIALOGUE_PATH},
            )
            break
        msg = json.loads(raw)
        msg_type = msg.get("type")
        if msg_type == "token":
            result_q.put(("token", msg["data"]))
        elif msg_type == "done":
            _handle_done(msg, result_q)
            break
        elif msg_type == "error":
            result_q.put(("error", RuntimeError(str(msg.get("data", "ws_error")))))
            break


def _handle_done(msg: dict, result_q: queue.Queue) -> None:
    """Parse a done frame and push the metadata event onto result_q.

    Args:
        msg: Parsed JSON message dict with type == "done".
        result_q: Queue to push the ("done", metadata) tuple onto.
    """
    metadata = dict(msg.get("data") or {})
    audio_b64: str | None = metadata.pop("audio_bytes_b64", None)
    metadata["audio_bytes"] = base64.b64decode(audio_b64) if audio_b64 else None
    result_q.put(("done", metadata))
