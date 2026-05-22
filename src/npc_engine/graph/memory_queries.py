"""
Module: memory_queries
Layer: graph
Purpose: Cypher string constants and read accessors for Memory nodes and REMEMBERS edges.
Does NOT: execute write operations or open transactions.
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.memory_service
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

CYPHER_CREATE_MEMORY = """
MERGE (m:Memory {id: $memory_id})
SET m.content = $content,
    m.vividness = $vividness,
    m.emotional_charge = $emotional_charge,
    m.created_at_game_time = $created_at_game_time,
    m.last_recalled_at = $last_recalled_at
WITH m
MATCH (c:Character {id: $character_id})
MERGE (c)-[:REMEMBERS {since_game_time: $since_game_time}]->(m)
RETURN m.id AS memory_id
"""

CYPHER_GET_MEMORIES_FOR_CHARACTER = """
MATCH (c:Character {id: $character_id})-[:REMEMBERS]->(m:Memory)
RETURN m.id AS id,
       m.content AS content,
       toInteger(m.vividness) AS vividness,
       toInteger(m.emotional_charge) AS emotional_charge,
       m.created_at_game_time AS created_at_game_time
ORDER BY m.vividness DESC
LIMIT $k
"""

CYPHER_DECAY_VIVIDNESS = """
MATCH (m:Memory)
WHERE toInteger(m.vividness) > 0
SET m.vividness = CASE
    WHEN toInteger(m.vividness) - $decay < 0 THEN 0
    ELSE toInteger(m.vividness) - $decay
END
RETURN count(m) AS affected
"""

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def get_memories_for_character(
    session: AsyncSession,
    *,
    character_id: str,
    k: int,
) -> list[dict[str, Any]]:
    """Fetch top-k memories for a character ordered by vividness descending.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        k: Maximum number of memories to return.

    Returns:
        List of dicts with id, content, vividness, emotional_charge,
        and created_at_game_time fields.
    """
    result = await session.run(
        CYPHER_GET_MEMORIES_FOR_CHARACTER,
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
