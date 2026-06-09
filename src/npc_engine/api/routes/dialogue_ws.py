"""
dialogue_ws.py - WebSocket endpoint for streamed dialogue token events.
Layer: api
Purpose: Stream dialogue token chunks over a WebSocket, capping concurrent
         connections per API key to prevent unmetered LLM amplification.
Does NOT: mutate relation or emotion state directly.
Dependencies injected: DialogueHandler.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
from collections.abc import Iterator
import re
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from npc_engine.api.dependencies import (
    build_dialogue_handler,
    get_graph_db,
    get_llm_client,
    get_llm_config,
)
from npc_engine.api.dependency_singletons import get_dialogue_engine_model_config
from npc_engine.api.schemas import DialogueRequest
from npc_engine.auth.api_key import resolve_scope_from_authorization
from npc_engine.config import get_settings
from npc_engine.engines.dialogue.dialogue_models import DialogueResponse
from npc_engine.engines.proactive_dialogue.models import ProactiveLine
from npc_engine.utils.errors import AuthError
from npc_engine.utils.logging import get_logger


router = APIRouter()
logger = get_logger(__name__)

# Maximum number of concurrent WebSocket connections allowed per API key.
# Requests that would exceed this cap are rejected before accepting the socket,
# preventing per-frame LLM calls from being used as an unmetered amplification vector.
MAX_WS_CONNECTIONS_PER_KEY: int = 5


def check_ws_connection_limit(current_count: int) -> bool:
    """Return True when a new WS connection may be opened for a given key.

    Args:
        current_count: Number of active WebSocket connections for this key.

    Returns:
        True when current_count is below MAX_WS_CONNECTIONS_PER_KEY.
    """
    return current_count < MAX_WS_CONNECTIONS_PER_KEY


# Active WebSocket connection counts keyed by a hash of the API key, guarded by a
# lock so the check-and-increment is atomic (L1-01: the cap was previously defined
# but never enforced at the endpoint).
_active_ws_connections: dict[str, int] = {}
_ws_connections_lock = asyncio.Lock()


def _ws_key_id(authorization: str) -> str:
    """Return a non-reversible per-key identity (SHA-256) for connection accounting."""
    return hashlib.sha256(authorization.encode("utf-8")).hexdigest()


async def _acquire_ws_slot(key_id: str) -> bool:
    """Atomically reserve a connection slot for key_id; False when already at cap."""
    async with _ws_connections_lock:
        current = _active_ws_connections.get(key_id, 0)
        if not check_ws_connection_limit(current):
            return False
        _active_ws_connections[key_id] = current + 1
        return True


async def _release_ws_slot(key_id: str) -> None:
    """Release one previously-acquired connection slot for key_id."""
    async with _ws_connections_lock:
        remaining = _active_ws_connections.get(key_id, 0) - 1
        if remaining > 0:
            _active_ws_connections[key_id] = remaining
        else:
            _active_ws_connections.pop(key_id, None)


def _build_done_data(response: DialogueResponse) -> dict[str, Any]:
    """Assemble the payload for the ``done`` WebSocket message.

    Includes all metadata fields plus ``audio_bytes_b64`` (base64-encoded WAV
    bytes) when TTS produced audio, or None when TTS is disabled or failed.

    Args:
        response: Fully resolved dialogue response from the handler.

    Returns:
        Dict safe to pass to ``websocket.send_json``.
    """
    audio_b64: str | None = (
        base64.b64encode(response.audio_bytes).decode()
        if response.audio_bytes
        else None
    )
    return {
        "degradation_level": response.degradation_level,
        "emotion": response.emotion,
        "relation_deltas": response.relation_deltas.model_dump(),
        "action": response.action.model_dump(),
        "facial_expression": response.facial_expression.model_dump(),
        "audio_bytes_b64": audio_b64,
    }


def _iter_token_chunks(text: str) -> Iterator[str]:
    """Split text into non-empty word chunks while preserving trailing whitespace."""

    for match in re.finditer(r"\S+\s*", text):
        chunk = match.group(0)
        if chunk != "":
            yield chunk


async def push_proactive_line(ws: WebSocket, line: ProactiveLine) -> None:
    """Send a proactive_line push message over an open WebSocket connection.

    This is a standalone helper used by (slice 2) scheduler wiring and any
    future caller that holds an open WebSocket and a ProactiveLine. It does
    NOT modify the existing dialogue WS handler loop.

    Args:
        ws: The already-accepted WebSocket connection to push to.
        line: ProactiveLine produced by ProactiveDialogueEngine.generate_line.
    """
    await ws.send_json(line.to_ws_message())


@router.websocket("/ws/dialogue")
async def dialogue_ws(websocket: WebSocket) -> None:
    """Stream token chunks for a dialogue request payload."""

    settings = get_settings()
    authorization = websocket.headers.get("Authorization", "")
    try:
        resolve_scope_from_authorization(authorization=authorization, settings=settings)
    except AuthError:
        await websocket.close(code=1008)
        return

    key_id = _ws_key_id(authorization)
    if not await _acquire_ws_slot(key_id):
        logger.warning("ws_connection_cap_reached", extra={"max": MAX_WS_CONNECTIONS_PER_KEY})
        await websocket.close(code=1008)
        return

    await websocket.accept()
    graph_db = get_graph_db()
    await graph_db.connect()
    try:
        async with graph_db.get_session() as session:
            payload = await websocket.receive_json()
            request = DialogueRequest.model_validate(payload)
            engine_model_config = get_dialogue_engine_model_config()
            handler = build_dialogue_handler(
                session=session,
                settings=settings,
                llm_client=get_llm_client(
                    settings=settings,
                    engine_model_config=engine_model_config,
                ),
                llm_config=get_llm_config(),
                engine_model_config=engine_model_config,
            )
            final_response = await handler.handle(request=request)
            for chunk in _iter_token_chunks(final_response.npc_response):
                await websocket.send_json({"type": "token", "data": chunk})
            await websocket.send_json({
                "type": "done",
                "data": _build_done_data(final_response),
            })
    except WebSocketDisconnect:
        return
    except Exception as error:
        logger.exception("ws_dialogue_error", extra={"detail": str(error)})
        await websocket.send_json({"type": "error", "data": "internal_error"})
        await websocket.close(code=1011)
    finally:
        await _release_ws_slot(key_id)
