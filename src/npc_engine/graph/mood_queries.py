"""
Module: mood_queries
Layer: graph
Purpose: Neo4j queries for mood-contagion data — co-located affectionate pairs and mood reads.
Does NOT: blend or compute mood values.
Dependencies: neo4j AsyncSession
Dependencies injected: AsyncSession (per call).
Used by: engines/mood/mood_contagion_engine
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession


LOGGER = logging.getLogger(__name__)

CYPHER_CO_LOCATED_AFFECTIONATE_PAIRS = """
MATCH (a:Character)-[:LOCATED_AT]->(l:Location)<-[:LOCATED_AT]-(b:Character)
WHERE a.id < b.id
  AND a.is_active = true
  AND b.is_active = true
MATCH (a)-[r:RELATES_TO]->(b)
WHERE r.affection > $affection_threshold
RETURN a.id AS npc_a, b.id AS npc_b, r.affection AS affection
"""

CYPHER_GET_CHARACTER_MOOD = """
MATCH (c:Character {id: $character_id})
RETURN c.current_mood AS mood, c.mood_intensity AS intensity
"""

CYPHER_SET_CHARACTER_MOOD = """
MATCH (c:Character {id: $character_id})
SET c.current_mood = $mood, c.mood_intensity = $intensity
"""

CYPHER_GET_ALL_CHARACTER_MOODS = """
MATCH (c:Character)
WHERE c.current_mood IS NOT NULL AND c.is_active = true
RETURN c.id AS character_id, c.current_mood AS mood, c.mood_intensity AS intensity
"""


async def get_co_located_affectionate_pairs(
    session: AsyncSession,
    affection_threshold: int = 50,
) -> list[tuple[str, str]]:
    """Return pairs of co-located NPCs whose RELATES_TO.affection exceeds the threshold.

    Each pair is returned once (a.id < b.id ensures deduplication).

    Args:
        session: Active Neo4j async session.
        affection_threshold: Minimum affection score (exclusive). Default 50.

    Returns:
        List of (npc_a_id, npc_b_id) tuples.
    """
    result = await session.run(
        CYPHER_CO_LOCATED_AFFECTIONATE_PAIRS,
        affection_threshold=affection_threshold,
    )
    return [(rec["npc_a"], rec["npc_b"]) async for rec in result]


async def get_character_mood(
    session: AsyncSession,
    character_id: str,
) -> tuple[str, float] | None:
    """Return stored mood label and intensity for a character.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.

    Returns:
        Tuple of (mood_label, intensity) or None if not set.
    """
    result = await session.run(CYPHER_GET_CHARACTER_MOOD, character_id=character_id)
    row = await result.single()
    if row is None or row["mood"] is None:
        return None
    return (row["mood"], float(row["intensity"] or 0.0))


async def set_character_mood(
    session: AsyncSession,
    character_id: str,
    mood: str,
    intensity: float,
) -> None:
    """Persist mood label and intensity to the Character node.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        mood: Mood label string (e.g. "neutral", "warm", "agitated").
        intensity: Mood intensity in [0.0, 1.0].
    """
    await session.run(
        CYPHER_SET_CHARACTER_MOOD,
        character_id=character_id,
        mood=mood,
        intensity=intensity,
    )


async def get_all_character_moods(
    session: AsyncSession,
) -> list[dict]:
    """Return all active characters with a stored mood.

    Args:
        session: Active Neo4j async session.

    Returns:
        List of dicts with keys ``character_id``, ``mood``, ``intensity``.
    """
    result = await session.run(CYPHER_GET_ALL_CHARACTER_MOODS)
    return [
        {
            "character_id": rec["character_id"],
            "mood": rec["mood"],
            "intensity": float(rec["intensity"] or 0.0),
        }
        async for rec in result
    ]
