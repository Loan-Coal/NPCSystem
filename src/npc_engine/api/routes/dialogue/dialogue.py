"""
Module: dialogue
Layer: api
Purpose: REST endpoints for dialogue — full-turn response and pending intent delivery.
Does NOT: implement dialogue orchestration logic or intent scoring.
Dependencies: engines.dialogue.dialogue_handler, engines.dialogue.system_state_context,
              graph.intent_queue_reader, graph.intent_queue_writer, api.schemas
Dependencies injected: DialogueHandler, AsyncSession, Settings.
Used by: api.main (router registration)
"""
from __future__ import annotations

from neo4j import AsyncSession
from fastapi import APIRouter, Depends, HTTPException

from npc_engine.api.dependencies import get_db_session, get_dialogue_handler, get_settings
from npc_engine.api.dependencies_engines import get_director_beat_log
from npc_engine.api.schemas import ConversationIntentResponse, DialogueRequest, DialogueResponse
from npc_engine.config import Settings
from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler
from npc_engine.engines.dialogue.system_state_context import resolve_system_state
from npc_engine.engines.director.director_beat_log import DirectorBeatLog, DirectorBeatRecord
from npc_engine.graph.intent_queue_reader import get_pending_intents as get_pending_intents_from_queue
from npc_engine.graph.intent_queue_writer import mark_delivered as mark_intent_delivered
from npc_engine.utils.errors import NodeNotFoundError
from npc_engine.utils.logging import get_logger

# Default number of recent director beats returned by the director-beats read route.
DEFAULT_DIRECTOR_BEAT_LIMIT: int = 10

_logger = get_logger(__name__)

# HTTP status for a dialogue referencing a Character node that does not exist (ISSUE-118).
_CHARACTER_NOT_FOUND_STATUS: int = 422

router = APIRouter()


@router.post("/dialogue", response_model=DialogueResponse)
async def dialogue(
    request: DialogueRequest,
    handler: DialogueHandler = Depends(get_dialogue_handler),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> DialogueResponse:
    """Run one dialogue turn and return final structured response.

    Resolves live system state (trade availability, quest status) before calling
    the handler so the NPC's response is grounded in engine reality (ISSUE-071).
    """
    system_ctx = await resolve_system_state(
        session=session,
        npc_id=request.npc_id,
        player_id=request.player_id,
        settings=settings,
    )
    try:
        return await handler.handle(request=request, system_state_context=system_ctx)
    except NodeNotFoundError as exc:
        # Redacted (L8-02): never echo the internal node id to the client; log it server-side.
        _logger.info("dialogue_character_not_found", extra={"node_id": exc.node_id})
        raise HTTPException(
            status_code=_CHARACTER_NOT_FOUND_STATUS,
            detail={"code": "CHARACTER_NOT_FOUND", "message": "Character not found."},
        ) from exc


@router.get("/dialogue/pending", response_model=list[ConversationIntentResponse])
async def get_pending_intents(
    player_id: str,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> list[ConversationIntentResponse]:
    """Fetch and consume pending NPC-initiated dialogue intents for a player.

    Returns intents ordered by score DESC. Each returned intent is immediately
    marked delivered — this endpoint is destructive; call it once per poll cycle.

    Args (query params):
        player_id: Character ID of the player to fetch intents for.

    Returns:
        List of ConversationIntentResponse (may be empty).
    """
    intents = await get_pending_intents_from_queue(session, player_id, settings=settings)
    responses: list[ConversationIntentResponse] = []
    for intent in intents:
        intent_id = f"{intent.npc_id}:{intent.player_id}:{intent.tick}:{intent.trigger_type}"
        await mark_intent_delivered(session, intent_id)
        responses.append(ConversationIntentResponse(
            intent_id=intent_id,
            npc_id=intent.npc_id,
            tick=intent.tick,
            score=intent.score,
            reason=intent.reason,
            trigger_type=intent.trigger_type,
            trigger_ref=intent.trigger_ref,
        ))
    return responses


@router.get("/dialogue/director-beats", response_model=list[DirectorBeatRecord])
async def get_recent_director_beats(
    limit: int = DEFAULT_DIRECTOR_BEAT_LIMIT,
    beat_log: DirectorBeatLog = Depends(get_director_beat_log),
) -> list[DirectorBeatRecord]:
    """Return the most recent drama-director beats, newest first (F2.4).

    Non-destructive (a peek): unlike /dialogue/pending, polling does not consume.
    The director tick records beats here when it injects one (F1.5).

    Args (query params):
        limit: Maximum number of recent beats to return.

    Returns:
        Newest-first list of DirectorBeatRecord (may be empty).
    """
    return beat_log.recent(limit=limit)
