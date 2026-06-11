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
    m.occurred_at_game_time = $occurred_at_game_time,
    m.is_historical = $is_historical,
    m.last_recalled_at = $last_recalled_at,
    m.subject_player_id = $subject_player_id,
    m.recall_count = coalesce(m.recall_count, 0)
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
       m.created_at_game_time AS created_at_game_time,
       m.occurred_at_game_time AS occurred_at_game_time,
       coalesce(m.is_historical, false) AS is_historical
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

CYPHER_GET_PLAYER_MEMORIES_FOR_NPC = """
MATCH (c:Character {id: $npc_id})-[:REMEMBERS]->(m:Memory)
WHERE m.subject_player_id = $player_id
RETURN m.id AS id,
       m.content AS content,
       toInteger(m.vividness) AS vividness,
       toInteger(m.emotional_charge) AS emotional_charge,
       m.subject_player_id AS subject_player_id,
       coalesce(toInteger(m.recall_count), 0) AS recall_count,
       coalesce(m.never_forget, false) AS never_forget,
       m.created_at_game_time AS created_at_game_time,
       m.occurred_at_game_time AS occurred_at_game_time,
       coalesce(m.is_historical, false) AS is_historical
ORDER BY m.vividness DESC
LIMIT $k
"""

CYPHER_DECAY_VIVIDNESS_WEIGHTED = """
MATCH (m:Memory)
WHERE toInteger(m.vividness) > 0
WITH m,
     $base_decay - (toInteger(coalesce(m.emotional_charge, 0)) / $charge_divisor) AS node_decay
WITH m, CASE WHEN node_decay < 1 THEN 1 ELSE node_decay END AS clamped_decay
SET m.vividness = CASE
    WHEN toInteger(m.vividness) - clamped_decay < 0 THEN 0
    ELSE toInteger(m.vividness) - clamped_decay
END
RETURN count(m) AS affected
"""

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def get_player_memories_for_npc(
    session: AsyncSession,
    *,
    npc_id: str,
    player_id: str,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Fetch memories this NPC holds that concern a specific player.

    Only returns memories whose ``subject_player_id`` matches ``player_id``.
    Results are ordered by vividness descending so the most vivid memories
    surface first.

    Args:
        session: Active Neo4j async session.
        npc_id: ID of the NPC character node.
        player_id: ID of the player whose memories to retrieve.
        k: Maximum number of memories to return.

    Returns:
        List of dicts with id, content, vividness, emotional_charge,
        subject_player_id, recall_count, never_forget, and
        created_at_game_time fields.
    """
    result = await session.run(
        CYPHER_GET_PLAYER_MEMORIES_FOR_NPC,
        npc_id=npc_id,
        player_id=player_id,
        k=k,
    )
    try:
        return cast(
            list[dict[str, Any]],
            [dict(record) async for record in result],
        )
    finally:
        await result.consume()


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
