"""
Module: relationship
Layer: api
Purpose: HTTP route for reading derived relationship standing between two NPCs.
         Returns the named Standing band plus raw trust/fear/affection scalars.
Does NOT: execute Cypher directly; delegates to RelationReader (graph layer).
Dependencies injected: RelationReader via FastAPI Depends.
Used by: npc_engine.main (registered at API_V1_PREFIX)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncSession
from pydantic import BaseModel, ConfigDict

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import ok_response
from npc_engine.engines.relationship.standing import Standing, derive_standing
from npc_engine.graph.relation_reader import RelationReader
from npc_engine.utils.errors import RelationEdgeNotFoundError


class RelationshipResponse(BaseModel):
    """Typed response payload for the NPC relationship standing endpoint."""

    standing: Standing
    trust: int
    fear: int
    affection: int

    model_config = ConfigDict(frozen=True)


router = APIRouter(prefix="/npc", tags=["relationship"])


def _get_relation_reader(session: AsyncSession = Depends(get_db_session)) -> RelationReader:
    """Build a RelationReader bound to the current request session.

    Args:
        session: Scoped Neo4j session injected by FastAPI.

    Returns:
        RelationReader for the current request.
    """
    return RelationReader(session=session)


@router.get("/{npc_id}/relationship/{other_id}", response_model=RelationshipResponse)
async def get_relationship_standing(
    npc_id: str,
    other_id: str,
    reader: RelationReader = Depends(_get_relation_reader),
) -> dict:
    """Return the derived standing and raw scalars for the directed relation npc_id → other_id.

    Args:
        npc_id: ID of the source NPC character.
        other_id: ID of the target NPC character.
        reader: Graph-layer reader injected by FastAPI.

    Returns:
        JSON envelope with standing (Standing enum value), trust, fear, affection.

    Raises:
        HTTPException 404: If no RELATES_TO edge exists between the two NPCs.
    """
    try:
        scalars = await reader.get_relation_scalars(src_id=npc_id, dst_id=other_id)
    except RelationEdgeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    standing = derive_standing(
        trust=scalars["trust"],
        fear=scalars["fear"],
        affection=scalars["affection"],
    )
    payload = RelationshipResponse(
        standing=standing,
        trust=scalars["trust"],
        fear=scalars["fear"],
        affection=scalars["affection"],
    )
    return ok_response(payload.model_dump())
