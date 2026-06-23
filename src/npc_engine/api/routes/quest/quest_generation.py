"""
Module: quest_generation
Layer: api
Purpose: Admin HTTP routes for generating quests and retrieving quest nodes.
Does NOT: implement quest lifecycle state transitions or call LLMs directly.
    Does NOT: pass a Neo4j session to the QuestGenerationEngine (DEC-122 / SEV-24).
Dependencies: engines.quest_generation.quest_generation_engine, graph.quest_node_service,
              api.dependencies.get_db_session, api.dependency_singletons
Dependencies injected: QuestGenerationEngine (via Depends); AsyncSession for admin graph
    routes only (list_drafts, mark_offered, get_quest_node).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncSession
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.dependency_singletons import get_quest_generation_engine
from npc_engine.api.helpers import OkEnvelope, error_response, ok_response
from npc_engine.engines.quest_generation.quest_generation_engine import QuestGenerationEngine
from npc_engine.graph.quest.quest_node_service import get_draft_quests, get_quest, offer_quest
from npc_engine.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/quests", tags=["quest_generation"])


class GenerateQuestRequest(BaseModel):
    """Request body for generating a new quest."""

    quest_giver_id: str = Field(..., min_length=1)

    model_config = ConfigDict(frozen=True)


class GenerateQuestPayload(BaseModel):
    """Typed payload for POST /quests/generate (SEV-16)."""

    quest_id: str
    description: str

    model_config = ConfigDict(frozen=True)


class DraftQuestsPayload(BaseModel):
    """Typed payload for GET /quests/drafts (SEV-16).

    ``drafts`` rows are heterogeneous quest node records, so each stays
    ``dict[str, Any]``.
    """

    drafts: list[dict[str, Any]]
    count: int

    model_config = ConfigDict(frozen=True)


class OfferedQuestPayload(BaseModel):
    """Typed payload for POST /quests/{quest_id}/offer (SEV-16)."""

    quest_id: str
    status: str

    model_config = ConfigDict(frozen=True)


class QuestNodePayload(BaseModel):
    """Typed payload for GET /quests/{quest_id} (SEV-16).

    ``quest`` is a heterogeneous quest node property bag, kept as ``dict[str, Any]``.
    """

    quest: dict[str, Any]

    model_config = ConfigDict(frozen=True)


@router.post("/generate", response_model=OkEnvelope[GenerateQuestPayload])
async def generate_quest(
    body: GenerateQuestRequest,
    engine: QuestGenerationEngine = Depends(get_quest_generation_engine),
) -> dict[str, Any]:
    """Generate a quest for a given NPC quest giver.

    Args:
        body: Request body containing the quest_giver_id.
        engine: Quest generation engine singleton.

    Returns:
        Envelope with quest_id and description.
    """
    try:
        result = await engine.generate(quest_giver_id=body.quest_giver_id)
    except ValueError as exc:
        logger.warning("quest_generation_failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=404,
            detail=error_response(
                error_code="QUEST_GENERATION_FAILED",
                message="Quest could not be generated for the given quest giver.",
            ),
        ) from exc
    return ok_response(
        GenerateQuestPayload(quest_id=result.quest_id, description=result.description).model_dump()
    )


@router.get("/drafts", response_model=OkEnvelope[DraftQuestsPayload])
async def list_draft_quests(
    quest_giver_id: str | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List all quest nodes with status='draft'.

    Args:
        quest_giver_id: Optional filter â€” only return drafts for this NPC.
        session: Active Neo4j async session.

    Returns:
        Envelope with ``drafts`` list and ``count``.
    """
    drafts = await get_draft_quests(session=session, quest_giver_id=quest_giver_id)
    return ok_response(DraftQuestsPayload(drafts=drafts, count=len(drafts)).model_dump())


@router.post("/{quest_id}/offer", response_model=OkEnvelope[OfferedQuestPayload])
async def offer_draft_quest_simple(
    quest_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Transition a draft quest to offered status.

    No player assignment or objective setup â€” this is the minimal designer-review
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
    return ok_response(
        OfferedQuestPayload(quest_id=result["quest_id"], status=result["status"]).model_dump()
    )


@router.get("/{quest_id}", response_model=OkEnvelope[QuestNodePayload])
async def get_quest_by_id(
    quest_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
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
    return ok_response(QuestNodePayload(quest=quest).model_dump())
