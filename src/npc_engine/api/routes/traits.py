"""
Module: traits
Layer: api
Purpose: HTTP routes for creating, reading, and removing character trait relationships.
Does NOT: perform authentication or implement trait logic.
Dependencies: graph.trait_service, api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main
"""

from __future__ import annotations

from neo4j import AsyncSession
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import ok_response
from npc_engine.graph.trait_service import add_trait, get_traits_svc, remove_trait

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class AddTraitRequest(BaseModel):
    """Request body for adding a trait to a character."""

    trait_id: str = Field(..., min_length=1)
    intensity: int = Field(..., ge=0, le=100)
    is_secret: bool = Field(default=False)

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/traits", tags=["traits"])


@router.post("/characters/{character_id}")
async def add_character_trait(
    character_id: str,
    body: AddTraitRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Create or update a HAS_TRAIT edge for a character.

    Args:
        character_id: ID of the character.
        body: Trait ID, intensity, and optional secrecy flag.

    Returns:
        Envelope confirming the trait assignment.
    """
    await add_trait(
        session,
        character_id=character_id,
        trait_id=body.trait_id,
        intensity=body.intensity,
        is_secret=body.is_secret,
    )
    return ok_response({"character_id": character_id, "trait_id": body.trait_id})


@router.get("/characters/{character_id}")
async def list_character_traits(
    character_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """List all traits for a character ordered by intensity descending.

    Args:
        character_id: ID of the character.

    Returns:
        Envelope with list of trait dicts.
    """
    traits = await get_traits_svc(session, character_id)
    return ok_response({"traits": traits})


@router.delete("/characters/{character_id}/{trait_id}")
async def remove_character_trait(
    character_id: str,
    trait_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Remove a HAS_TRAIT edge from a character.

    Args:
        character_id: ID of the character.
        trait_id: ID of the trait to remove.

    Returns:
        Envelope confirming removal.
    """
    await remove_trait(session, character_id=character_id, trait_id=trait_id)
    return ok_response({"character_id": character_id, "trait_id": trait_id})
