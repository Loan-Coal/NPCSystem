"""
Module: quest_generation
Layer: api
Purpose: Admin HTTP routes for generating quests and retrieving quest nodes.
Does NOT: implement quest lifecycle state transitions or call LLMs directly.
Dependencies: engines.quest_generation.quest_generation_engine, graph.quest_node_service,
              api.dependencies.get_db_session, api.dependency_singletons
Dependencies injected: AsyncSession (via FastAPI Depends), QuestGenerationEngine (via Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncSession
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.dependency_singletons import get_quest_generation_engine
from npc_engine.api.route_helpers import ok_response
from npc_engine.engines.quest_generation.quest_generation_engine import QuestGenerationEngine
from npc_engine.graph.quest_node_service import get_draft_quests, get_quest, offer_quest

router = APIRouter(prefix="/quests", tags=["quest_generation"])


class GenerateQuestRequest(BaseModel):
    """Request body for generating a new quest."""

    quest_giver_id: str = Field(..., min_length=1)

    model_config = ConfigDict(frozen=True)


@router.post("/generate")
async def generate_quest(
    body: GenerateQuestRequest,
    session: AsyncSession = Depends(get_db_session),
    engine: QuestGenerationEngine = Depends(get_quest_generation_engine),
) -> dict:
    """Generate a quest for a given NPC quest giver.

    Args:
        body: Request body containing the quest_giver_id.
        session: Active Neo4j async session.
        engine: Quest generation engine singleton.

    Returns:
        Envelope with quest_id and description.
    """
    try:
        result = await engine.generate(session=session, quest_giver_id=body.quest_giver_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok_response({"quest_id": result.quest_id, "description": result.description})


@router.get("/drafts")
async def list_draft_quests(
    quest_giver_id: str | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """List all quest nodes with status='draft'.

    Args:
        quest_giver_id: Optional filter — only return drafts for this NPC.
        session: Active Neo4j async session.

    Returns:
        Envelope with ``drafts`` list and ``count``.
    """
    drafts = await get_draft_quests(session=session, quest_giver_id=quest_giver_id)
    return ok_response({"drafts": drafts, "count": len(drafts)})


@router.post("/{quest_id}/offer")
async def offer_draft_quest_simple(
    quest_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Transition a draft quest to offered status.

    No player assignment or objective setup — this is the minimal designer-review
    path that marks a generated draft as ready to be seen by players.

    Args:
        quest_id: ID of the draft Quest node to offer.
        session: Active Neo4j async session.

    Returns:
        Envelope with the updated quest_id and status.

    Raises:
        HTTPException 404: When the quest does not exist or is not in draft status.
    """
    result = await offer_quest(session=session, quest_id=quest_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Draft quest '{quest_id}' not found (may not exist or already offered)",
        )
    return ok_response({"quest_id": result["quest_id"], "status": result["status"]})


@router.get("/{quest_id}")
async def get_quest_by_id(
    quest_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Retrieve a quest node by ID.

    Args:
        quest_id: ID of the Quest node to retrieve.
        session: Active Neo4j async session.

    Returns:
        Envelope with the quest node properties.
    """
    quest = await get_quest(session=session, quest_id=quest_id)
    if quest is None:
        raise HTTPException(status_code=404, detail=f"Quest '{quest_id}' not found")
    return ok_response({"quest": quest})
