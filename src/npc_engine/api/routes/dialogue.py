"""
Module: dialogue
Layer: api
Purpose: REST endpoints for dialogue — full-turn response and pending intent delivery.
Does NOT: implement dialogue orchestration logic or intent scoring.
Dependencies: engines.dialogue.dialogue_handler, graph.intent_queue_reader,
              graph.intent_queue_writer, api.schemas
Dependencies injected: DialogueHandler, AsyncSession, Settings.
Used by: api.main (router registration)
"""
from __future__ import annotations

from neo4j import AsyncSession
from fastapi import APIRouter, Depends

from npc_engine.api.dependencies import get_db_session, get_dialogue_handler, get_settings
from npc_engine.api.schemas import ConversationIntentResponse, DialogueRequest, DialogueResponse
from npc_engine.config import Settings
from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler
from npc_engine.graph.intent_queue_reader import get_pending_intents as get_pending_intents_from_queue
from npc_engine.graph.intent_queue_writer import mark_delivered as mark_intent_delivered

router = APIRouter()


@router.post("/dialogue", response_model=DialogueResponse)
async def dialogue(
    request: DialogueRequest,
    handler: DialogueHandler = Depends(get_dialogue_handler),
) -> DialogueResponse:
    """Run one dialogue turn and return final structured response."""
    return await handler.handle(request=request)


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
