"""
Module: skills
Layer: api
Purpose: HTTP routes for creating character skill edges and querying skill data.
Does NOT: perform authentication or implement skill logic.
Dependencies: graph.skill_service, api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main
"""

from __future__ import annotations

from neo4j import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.route_helpers import ok_response
from npc_engine.graph.skill_service import (
    add_skill,
    check_skill_threshold_svc,
    get_characters_with_skill_svc,
    get_skills_svc,
    increment_xp,
)

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class AddSkillRequest(BaseModel):
    """Request body for adding a skill to a character."""

    skill_id: str = Field(..., min_length=1)
    level: int = Field(..., ge=0, le=100)
    xp: int = Field(default=0, ge=0)

    model_config = ConfigDict(frozen=True)


class IncrementXpRequest(BaseModel):
    """Request body for adding XP to a character skill."""

    xp_delta: int = Field(..., gt=0)
    tick: int = Field(default=0, ge=0)

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/skills", tags=["skills"])


@router.post("/characters/{character_id}")
async def add_character_skill(
    character_id: str,
    body: AddSkillRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Create or update a HAS_SKILL edge for a character.

    Args:
        character_id: ID of the character.
        body: Skill ID, initial level, and optional initial XP.

    Returns:
        Envelope confirming the skill assignment.
    """
    await add_skill(
        session,
        character_id=character_id,
        skill_id=body.skill_id,
        level=body.level,
        xp=body.xp,
    )
    return ok_response({"character_id": character_id, "skill_id": body.skill_id})


@router.get("/characters/{character_id}")
async def list_character_skills(
    character_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """List all skills for a character.

    Args:
        character_id: ID of the character.

    Returns:
        Envelope with list of skill dicts ordered by level descending.
    """
    skills = await get_skills_svc(session, character_id)
    return ok_response({"skills": skills})


@router.post("/characters/{character_id}/xp")
async def award_xp(
    character_id: str,
    body: IncrementXpRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Award XP to a character skill and return the new level.

    Args:
        character_id: ID of the character.
        body: Skill ID is provided in the path; body contains xp_delta and optional tick.

    Returns:
        Envelope with new_level after the XP grant.
    """
    raise HTTPException(status_code=422, detail="skill_id must be provided as query param; use /skills/characters/{character_id}/{skill_id}/xp")


@router.post("/characters/{character_id}/{skill_id}/xp")
async def award_xp_for_skill(
    character_id: str,
    skill_id: str,
    body: IncrementXpRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Award XP to a specific skill for a character.

    Args:
        character_id: ID of the character.
        skill_id: ID of the skill.
        body: XP delta and optional tick.

    Returns:
        Envelope with new_level after the XP grant.
    """
    new_level = await increment_xp(
        session,
        character_id=character_id,
        skill_id=skill_id,
        xp_delta=body.xp_delta,
        tick=body.tick,
    )
    return ok_response({"character_id": character_id, "skill_id": skill_id, "new_level": new_level})


@router.get("/characters/{character_id}/{skill_id}/check")
async def check_skill(
    character_id: str,
    skill_id: str,
    min_level: int = 0,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Check whether a character meets a minimum skill threshold.

    Args:
        character_id: ID of the character.
        skill_id: ID of the skill.
        min_level: Required minimum level.

    Returns:
        Envelope with meets_threshold boolean.
    """
    meets = await check_skill_threshold_svc(
        session,
        character_id=character_id,
        skill_id=skill_id,
        min_level=min_level,
    )
    return ok_response({"meets_threshold": meets})


@router.get("/{skill_id}/characters")
async def list_characters_with_skill(
    skill_id: str,
    min_level: int = 0,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """List active characters that have a skill at or above a minimum level.

    Args:
        skill_id: ID of the skill.
        min_level: Minimum level filter (default 0 = any level).

    Returns:
        Envelope with list of character dicts.
    """
    characters = await get_characters_with_skill_svc(session, skill_id, min_level)
    return ok_response({"characters": characters})
