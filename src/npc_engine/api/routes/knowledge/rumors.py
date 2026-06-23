"""
Module: rumors
Layer: api
Purpose: Admin HTTP routes for creating and querying Rumor nodes and BELIEVES_RUMOR edges.
Does NOT: perform authentication or validate auth scopes directly.
Dependencies: graph.rumor_service, api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.helpers import OkEnvelope, ok_response
from npc_engine.graph.gossip.rumor_service import (
    believe_rumor,
    create_rumor,
    get_rumor_tree_svc,
    get_rumors_about_event_svc,
    get_rumors_for_character_svc,
)

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateRumorRequest(BaseModel):
    """Request body for creating a root Rumor node."""

    content: str = Field(..., min_length=1, max_length=2048)
    origin_event_id: str | None = Field(default=None)
    created_at_tick: int = Field(..., ge=0)
    severity: int = Field(..., ge=0, le=100)
    is_fabricated: bool = Field(default=False)

    model_config = ConfigDict(frozen=True)


class BelieveRumorRequest(BaseModel):
    """Request body for recording a character's belief in a rumor."""

    character_id: str = Field(..., min_length=1)
    confidence: int = Field(..., ge=0, le=100)
    tick: int = Field(..., ge=0)
    from_character_id: str | None = Field(default=None)

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/rumors", tags=["rumors"])


@router.post("", response_model=OkEnvelope[dict[str, Any]])
async def create_rumor_route(
    body: CreateRumorRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create (or merge) a root Rumor node.

    Args:
        body: Rumor content, origin event, tick, severity, and fabrication flag.

    Returns:
        Envelope with the rumor_id.
    """
    rumor_id = await create_rumor(
        session,
        content=body.content,
        origin_event_id=body.origin_event_id,
        created_at_tick=body.created_at_tick,
        severity=body.severity,
        is_fabricated=body.is_fabricated,
    )
    return ok_response({"rumor_id": rumor_id})


@router.post("/{rumor_id}/believe", response_model=OkEnvelope[dict[str, Any]])
async def believe_rumor_route(
    rumor_id: str,
    body: BelieveRumorRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Record a character's belief in a rumor.

    Args:
        rumor_id: ID of the Rumor node.
        body: Character ID, confidence, tick, and optional source character.

    Returns:
        Envelope confirming the belief edge.
    """
    await believe_rumor(
        session,
        character_id=body.character_id,
        rumor_id=rumor_id,
        confidence=body.confidence,
        tick=body.tick,
        from_character_id=body.from_character_id,
    )
    return ok_response({"rumor_id": rumor_id, "character_id": body.character_id})


@router.get("/{character_id}", response_model=OkEnvelope[dict[str, Any]])
async def list_rumors_for_character(
    character_id: str,
    min_confidence: int = 30,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List rumors a character believes.

    Args:
        character_id: ID of the character.
        min_confidence: Minimum confidence threshold (default 30).

    Returns:
        Envelope with list of rumor belief dicts ordered by confidence.
    """
    rumors = await get_rumors_for_character_svc(
        session, character_id=character_id, min_confidence=min_confidence
    )
    return ok_response({"rumors": rumors})


@router.get("/tree/{rumor_id}", response_model=OkEnvelope[dict[str, Any]])
async def get_rumor_tree_route(
    rumor_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Fetch the full derivation tree of a rumor.

    Args:
        rumor_id: ID of the root Rumor node.

    Returns:
        Envelope with list of derived rumor dicts.
    """
    tree = await get_rumor_tree_svc(session, rumor_id=rumor_id)
    return ok_response({"tree": tree})


@router.get("/event/{event_id}", response_model=OkEnvelope[dict[str, Any]])
async def get_rumors_about_event_route(
    event_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Fetch rumors originating from a specific event.

    Args:
        event_id: ID of the originating Event node.

    Returns:
        Envelope with list of rumor dicts.
    """
    rumors = await get_rumors_about_event_svc(session, event_id=event_id)
    return ok_response({"rumors": rumors})
