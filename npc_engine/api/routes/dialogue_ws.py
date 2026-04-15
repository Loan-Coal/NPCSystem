"""
dialogue_ws.py - WebSocket endpoint for streamed dialogue token events.

Does NOT: mutate relation or emotion state directly.

Dependencies injected: DialogueHandler.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.dependencies import (
    get_embedding_index,
    get_emotion_updater,
    get_graph_db,
    get_llm_client,
    get_session_store,
)
from api.schemas import DialogueRequest
from engines.dialogue.dialogue_handler import DialogueHandler
from config import get_settings
from auth.api_key import validate_bearer_token
from utils.errors import AuthError
from utils.logging import get_logger


router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws/dialogue")
async def dialogue_ws(websocket: WebSocket) -> None:
    """Stream token chunks for a dialogue request payload."""

    settings = get_settings()
    authorization = websocket.headers.get("Authorization", "")
    try:
        validate_bearer_token(authorization=authorization, expected_secret=settings.API_KEY_SECRET)
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
            handler = DialogueHandler(
                session=session,
                settings=settings,
                llm_client=get_llm_client(settings=settings),
                session_store=get_session_store(),
                emotion_updater=get_emotion_updater(),
                embedding_index=get_embedding_index(),
            )
            final_response = await handler.handle(request=request)
            chunks = [token + " " for token in final_response.npc_response.split()]
            for chunk in chunks:
                await websocket.send_json({"type": "token", "data": chunk})
            await websocket.send_json({"type": "action", "data": final_response.action.model_dump()})
            await websocket.send_json({"type": "expression", "data": final_response.facial_expression.model_dump()})
            await websocket.send_json({"type": "done"})
    except WebSocketDisconnect:
        return
    except Exception as error:
        logger.exception("ws_dialogue_error", extra={"detail": str(error)})
        await websocket.send_json({"type": "error", "data": "internal_error"})
        await websocket.close(code=1011)
