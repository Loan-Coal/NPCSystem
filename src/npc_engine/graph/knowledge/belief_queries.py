"""
Module: belief_queries
Layer: graph
Purpose: Cypher string constants and read accessors for Belief nodes and BELIEVES edges.
Does NOT: execute write operations, open transactions, or call any LLM.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession (per call).
Used by: npc_engine.graph.knowledge.belief_service, npc_engine.engines.knowledge_learning.knowledge_extraction_engine
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Dedup / conflict detection
# ---------------------------------------------------------------------------

CYPHER_FIND_CONFLICTING_BELIEF = """
MATCH (c:Character {id: $character_id})-[:BELIEVES]->(b:Belief)
WHERE toLower(b.content) = toLower($content)
RETURN b.id AS id,
       b.content AS content,
       toInteger(b.confidence) AS confidence,
       b.created_at_game_time AS created_at_game_time
LIMIT 1
"""

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
MATCH (c:Character {id: $character_id})-[r:BELIEVES]->(b:Belief)
RETURN b.id AS id,
       b.content AS content,
       toInteger(b.confidence) AS confidence,
       b.created_at_game_time AS created_at_game_time,
       coalesce(r.is_deception, false) AS is_deception
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
        List of dicts with id, content, confidence, created_at_game_time, and
        is_deception (the BELIEVES-edge flag; False when unset) fields. The flag is a
        buyer-facing "tell" marking deliberately false beliefs without altering content.
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


async def find_conflicting_belief(
    session: AsyncSession,
    *,
    character_id: str,
    content: str,
) -> dict[str, Any] | None:
    """Return an existing belief that duplicates the candidate content, or None.

    Duplicate detection is case-insensitive exact-content match (slice 1).
    Semantic contradiction detection is deferred to slice 2.

    Args:
        session: Active Neo4j async session (read-only use; no write).
        character_id: ID of the character whose beliefs are searched.
        content: Candidate belief content string to test for duplication.

    Returns:
        Dict with id, content, confidence, created_at_game_time if a match
        is found; None otherwise.
    """
    result = await session.run(
        CYPHER_FIND_CONFLICTING_BELIEF,
        character_id=character_id,
        content=content,
    )
    try:
        records = [dict(record) async for record in result]
    finally:
        await result.consume()
    return records[0] if records else None
