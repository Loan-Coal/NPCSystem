"""
Module: dialogue_ws
Layer: demo_game
Purpose: WebSocket dialogue streaming client for the demo game. Connects to the
         engine's /v1/ws/dialogue endpoint, forwards token chunks and completion
         metadata through a queue for the main thread to consume each frame.
Dependencies: websockets (via uvicorn[standard] transitive dep), json, queue
Used by: demo_game.game_controller
"""

from __future__ import annotations

import base64
import json
import queue

import websockets.sync.client

_WS_DIALOGUE_PATH = "/v1/ws/dialogue"


def dialogue_ws_worker(
    ws_url: str,
    api_key: str,
    payload: dict,
    result_q: queue.Queue,
) -> None:
    """Stream dialogue tokens via WebSocket and push typed events onto result_q.

    Connects synchronously (safe to call from a daemon thread). Sends the
    dialogue request JSON and consumes the server message stream.

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
    """
    uri = ws_url.rstrip("/") + _WS_DIALOGUE_PATH
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        with websockets.sync.client.connect(uri, additional_headers=headers) as ws:
            ws.send(json.dumps(payload))
            while True:
                raw = ws.recv()
                msg = json.loads(raw)
                msg_type = msg.get("type")
                if msg_type == "token":
                    result_q.put(("token", msg["data"]))
                elif msg_type == "done":
                    metadata = dict(msg.get("data") or {})
                    audio_b64: str | None = metadata.pop("audio_bytes_b64", None)
                    metadata["audio_bytes"] = base64.b64decode(audio_b64) if audio_b64 else None
                    result_q.put(("done", metadata))
                    break
                elif msg_type == "error":
                    result_q.put(("error", RuntimeError(str(msg.get("data", "ws_error")))))
                    break
    except Exception as exc:
        result_q.put(("error", exc))
