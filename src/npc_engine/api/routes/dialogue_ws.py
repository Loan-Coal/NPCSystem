"""
dialogue_ws.py - WebSocket endpoint for streamed dialogue token events.

Does NOT: mutate relation or emotion state directly.

Dependencies injected: DialogueHandler.
"""

from collections.abc import Iterator
import re

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
from npc_engine.utils.errors import AuthError
from npc_engine.utils.logging import get_logger


router = APIRouter()
logger = get_logger(__name__)


def _iter_token_chunks(text: str) -> Iterator[str]:
    """Split text into non-empty word chunks while preserving trailing whitespace."""

    for match in re.finditer(r"\S+\s*", text):
        chunk = match.group(0)
        if chunk != "":
            yield chunk


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
                "data": {
                    "degradation_level": final_response.degradation_level,
                    "emotion": final_response.emotion,
                    "relation_deltas": final_response.relation_deltas.model_dump(),
                    "action": final_response.action.model_dump(),
                    "facial_expression": final_response.facial_expression.model_dump(),
                },
            })
    except WebSocketDisconnect:
        return
    except Exception as error:
        logger.exception("ws_dialogue_error", extra={"detail": str(error)})
        await websocket.send_json({"type": "error", "data": "internal_error"})
        await websocket.close(code=1011)
