"""
Module: skill_service
Layer: graph
Purpose: Create and manage character skill levels via HAS_SKILL edges.
Does NOT: implement business logic or call LLMs.
Dependencies: graph.skill_queries
Dependencies injected: AsyncSession.
Used by: npc_engine.engines.skill.skill_progression_engine, npc_engine.api.routes.skills
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.character.skill_queries import (
    CYPHER_INCREMENT_XP,
    CYPHER_MERGE_HAS_SKILL,
    XP_PER_LEVEL,
    check_skill_threshold,
    get_characters_with_skill,
    get_skills,
)


async def add_skill(
    session: AsyncSession,
    *,
    character_id: str,
    skill_id: str,
    level: int,
    xp: int = 0,
) -> None:
    """Create or update a HAS_SKILL edge between a character and a skill.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node.
        skill_id: ID of the Skill node.
        level: Initial skill level (0–100).
        xp: Initial XP value.
    """
    await session.run(
        CYPHER_MERGE_HAS_SKILL,
        character_id=character_id,
        skill_id=skill_id,
        level=level,
        xp=xp,
    )


async def get_skills_svc(
    session: AsyncSession,
    character_id: str,
) -> list[dict[str, Any]]:
    """Return all skills for a character ordered by level descending.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node.

    Returns:
        List of skill dicts.
    """
    return await get_skills(session, character_id=character_id)


async def increment_xp(
    session: AsyncSession,
    *,
    character_id: str,
    skill_id: str,
    xp_delta: int,
    tick: int = 0,
) -> int:
    """Add XP to a skill and update the level accordingly.

    Level = min(100, total_xp // XP_PER_LEVEL).

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node.
        skill_id: ID of the Skill node.
        xp_delta: Amount of XP to add (must be positive).
        tick: Current game tick; written as last_used_at_tick.

    Returns:
        New skill level after the XP increment.
    """
    result = await session.run(
        CYPHER_INCREMENT_XP,
        character_id=character_id,
        skill_id=skill_id,
        xp_delta=xp_delta,
        xp_per_level=XP_PER_LEVEL,
        tick=tick,
    )
    record = await result.single()
    if record is None:
        return 0
    return int(record["new_level"])


async def get_characters_with_skill_svc(
    session: AsyncSession,
    skill_id: str,
    min_level: int = 0,
) -> list[dict[str, Any]]:
    """Fetch active characters with a skill at or above the minimum level.

    Args:
        session: Active Neo4j async session.
        skill_id: ID of the Skill node.
        min_level: Minimum level threshold.

    Returns:
        List of dicts with character_id, character_name, level.
    """
    return await get_characters_with_skill(session, skill_id=skill_id, min_level=min_level)


async def check_skill_threshold_svc(
    session: AsyncSession,
    *,
    character_id: str,
    skill_id: str,
    min_level: int,
) -> bool:
    """Check whether a character meets a minimum skill level.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node.
        skill_id: ID of the Skill node.
        min_level: Required minimum level.

    Returns:
        True if the character has the skill at or above min_level; False otherwise.
    """
    return await check_skill_threshold(
        session,
        character_id=character_id,
        skill_id=skill_id,
        min_level=min_level,
    )
