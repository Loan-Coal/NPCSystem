"""
Module: skill_queries
Layer: graph
Purpose: Cypher queries for Skill nodes and HAS_SKILL edges.
Does NOT: implement business logic or call LLMs.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.skill_service
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# XP → level conversion constant (1 level per 100 XP, capped at 100)
# ---------------------------------------------------------------------------

XP_PER_LEVEL = 100

# ---------------------------------------------------------------------------
# Write queries
# ---------------------------------------------------------------------------

CYPHER_MERGE_HAS_SKILL = """
MATCH (c:Character {id: $character_id}), (s:Skill {id: $skill_id})
MERGE (c)-[e:HAS_SKILL]->(s)
ON CREATE SET e.level = $level, e.xp = $xp, e.last_used_at_tick = null
ON MATCH SET  e.level = $level, e.xp = $xp
"""

CYPHER_INCREMENT_XP = """
MATCH (c:Character {id: $character_id})-[e:HAS_SKILL]->(s:Skill {id: $skill_id})
SET e.xp = e.xp + $xp_delta,
    e.level = toInteger(CASE
        WHEN toInteger(e.xp + $xp_delta) / $xp_per_level > 100 THEN 100
        ELSE toInteger(e.xp + $xp_delta) / $xp_per_level
    END),
    e.last_used_at_tick = $tick
RETURN toInteger(e.level) AS new_level
"""

# ---------------------------------------------------------------------------
# Read queries
# ---------------------------------------------------------------------------

CYPHER_GET_SKILLS = """
MATCH (c:Character {id: $character_id})-[e:HAS_SKILL]->(s:Skill)
RETURN s.id AS skill_id,
       s.name AS name,
       s.category AS category,
       s.description AS description,
       toInteger(e.level) AS level,
       toInteger(e.xp) AS xp,
       e.last_used_at_tick AS last_used_at_tick
ORDER BY e.level DESC
"""

CYPHER_GET_CHARACTERS_WITH_SKILL = """
MATCH (c:Character)-[e:HAS_SKILL]->(s:Skill {id: $skill_id})
WHERE toInteger(e.level) >= $min_level
  AND c.is_active = true
RETURN c.id AS character_id,
       c.name AS character_name,
       toInteger(e.level) AS level
ORDER BY e.level DESC
"""

CYPHER_CHECK_SKILL_THRESHOLD = """
MATCH (c:Character {id: $character_id})-[e:HAS_SKILL]->(s:Skill {id: $skill_id})
RETURN toInteger(e.level) >= $min_level AS meets_threshold
"""

CYPHER_COMPLETED_QUESTS_WITH_SKILLS = """
MATCH (q:Quest {status: 'completed'})
WHERE q.completed_at_tick = $tick_id
MATCH (q)-[:BASED_ON]->(qt:QuestTemplate)-[r:REQUIRES_SKILL]->(s:Skill)
MATCH (c:Character)-[:PARTICIPATED_IN]->(q)
RETURN q.id AS quest_id,
       c.id AS character_id,
       s.id AS skill_id,
       toInteger(r.min_level) AS min_level
"""


async def get_skills(
    session: AsyncSession,
    *,
    character_id: str,
) -> list[dict[str, Any]]:
    """Fetch all skills for a character ordered by level descending.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node.

    Returns:
        List of skill dicts with skill_id, name, category, level, xp fields.
    """
    result = await session.run(CYPHER_GET_SKILLS, character_id=character_id)
    return cast(list[dict[str, Any]], [dict(record) async for record in result])


async def get_characters_with_skill(
    session: AsyncSession,
    *,
    skill_id: str,
    min_level: int = 0,
) -> list[dict[str, Any]]:
    """Fetch active characters that have a skill above the given minimum level.

    Args:
        session: Active Neo4j async session.
        skill_id: ID of the Skill node.
        min_level: Minimum level threshold (0–100).

    Returns:
        List of dicts with character_id, character_name, level.
    """
    result = await session.run(
        CYPHER_GET_CHARACTERS_WITH_SKILL,
        skill_id=skill_id,
        min_level=min_level,
    )
    return cast(list[dict[str, Any]], [dict(record) async for record in result])


async def check_skill_threshold(
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
    result = await session.run(
        CYPHER_CHECK_SKILL_THRESHOLD,
        character_id=character_id,
        skill_id=skill_id,
        min_level=min_level,
    )
    record = await result.single()
    if record is None:
        return False
    return bool(record["meets_threshold"])


async def get_completed_quests_with_skills(
    session: AsyncSession,
    *,
    tick_id: int,
) -> list[dict[str, Any]]:
    """Return (quest, character, skill) rows for quests completed this tick.

    Used by SkillProgressionEngine to award XP after quest completion.

    Args:
        session: Active Neo4j async session.
        tick_id: The game tick at which quests were completed.

    Returns:
        List of dicts with keys quest_id, character_id, skill_id, min_level.
    """
    result = await session.run(CYPHER_COMPLETED_QUESTS_WITH_SKILLS, tick_id=tick_id)
    return cast(list[dict[str, Any]], [dict(record) async for record in result])
