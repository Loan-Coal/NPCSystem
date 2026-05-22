"""
Module: belief_queries
Layer: graph
Purpose: Cypher string constants and read accessor for Belief nodes and BELIEVES edges.
Does NOT: execute write operations or open transactions.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.belief_service
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

CYPHER_CREATE_BELIEF = """
MERGE (b:Belief {id: $belief_id})
SET b.content = $content,
    b.confidence = $confidence,
    b.created_at_game_time = $created_at_game_time
WITH b
MATCH (c:Character {id: $character_id})
MERGE (c)-[:BELIEVES]->(b)
RETURN b.id AS belief_id
"""

CYPHER_GET_BELIEFS_FOR_CHARACTER = """
MATCH (c:Character {id: $character_id})-[:BELIEVES]->(b:Belief)
RETURN b.id AS id,
       b.content AS content,
       toInteger(b.confidence) AS confidence,
       b.created_at_game_time AS created_at_game_time
ORDER BY b.confidence DESC
LIMIT $k
"""

CYPHER_UPDATE_CONFIDENCE = """
MATCH (b:Belief {id: $belief_id})
SET b.confidence = $confidence
"""

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def get_beliefs_for_character(
    session: AsyncSession,
    *,
    character_id: str,
    k: int,
) -> list[dict[str, Any]]:
    """Fetch top-k beliefs for a character ordered by confidence descending.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        k: Maximum number of beliefs to return.

    Returns:
        List of dicts with id, content, confidence, and created_at_game_time fields.
    """
    result = await session.run(
        CYPHER_GET_BELIEFS_FOR_CHARACTER,
        character_id=character_id,
        k=k,
    )
    try:
        return cast(
            list[dict[str, Any]],
            [dict(record) async for record in result],
        )
    finally:
        await result.consume()
