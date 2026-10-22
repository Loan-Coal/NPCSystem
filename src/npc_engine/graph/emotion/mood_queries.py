"""
Module: mood_queries
Layer: graph
Purpose: Neo4j query for reading a character's stored mood label and intensity.
Does NOT: blend or compute mood values.
Dependencies: neo4j AsyncSession
Dependencies injected: AsyncSession (per call).
Used by: graph/repositories/quest_generation_repository
"""

from __future__ import annotations

from neo4j import AsyncSession


CYPHER_GET_CHARACTER_MOOD = """
MATCH (c:Character {id: $character_id})
RETURN c.current_mood AS mood, c.mood_intensity AS intensity
"""


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
