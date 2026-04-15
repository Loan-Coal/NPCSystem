"""
npc_state.py - Read endpoints for NPC state and emotion snapshots.

Does NOT: perform dialogue generation.

Dependencies injected: AsyncSession, EmotionStore.
"""

from fastapi import APIRouter, Depends
from neo4j import AsyncSession

from api.dependencies import get_db_session, get_emotion_store
from api.schemas import EmotionResponse, NPCStateResponse
from engines.emotion.emotion_store import EmotionStore
from graph.graph_reader import get_character_with_relations, get_events_for_npc


router = APIRouter()


@router.get("/npc/{npc_id}/state", response_model=NPCStateResponse)
async def npc_state(
    npc_id: str,
    include_relations: bool = True,
    include_events: bool = True,
    session: AsyncSession = Depends(get_db_session),
) -> NPCStateResponse:
    """Return compact NPC graph state snapshot."""

    character_bundle = await get_character_with_relations(session=session, npc_id=npc_id)
    events = await get_events_for_npc(session=session, npc_id=npc_id, limit=10) if include_events else []
    return NPCStateResponse(
        character=character_bundle.get("character"),
        relations=character_bundle.get("relations", []) if include_relations else [],
        events=events,
    )


@router.get("/npc/{npc_id}/emotion", response_model=EmotionResponse)
async def npc_emotion(npc_id: str, emotion_store: EmotionStore = Depends(get_emotion_store)) -> EmotionResponse:
    """Return current in-memory emotion snapshot for NPC."""

    state = emotion_store.get(npc_id=npc_id)
    return EmotionResponse(
        npc_id=npc_id,
        label=state.label,
        valence=state.valence,
        arousal=state.arousal,
        updated_at=state.updated_at.isoformat(),
    )
