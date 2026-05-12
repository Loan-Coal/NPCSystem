"""
Module: secret_queries
Layer: graph
Purpose: Cypher query strings and read accessors for Secret nodes and KNOWS_SECRET edges.
Does NOT: execute business logic or validate payloads.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.secret_service
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Write queries
# ---------------------------------------------------------------------------

CYPHER_CREATE_SECRET_NODE = """
MERGE (s:Secret {id: $secret_id})
SET s.content = $content,
    s.severity = $severity,
    s.created_at = $created_at
WITH s
MATCH (c:Character {id: $character_id})
MERGE (c)-[:KNOWS_SECRET {knowledge_state: 'knows', source_character_id: $character_id}]->(s)
RETURN s.id AS secret_id
"""

# ---------------------------------------------------------------------------
# Read queries
# ---------------------------------------------------------------------------

CYPHER_GET_SECRETS_FOR_CHARACTER = """
MATCH (c:Character {id: $character_id})-[:KNOWS_SECRET]->(s:Secret)
RETURN s.id AS id,
       s.content AS content,
       toInteger(s.severity) AS severity,
       s.created_at AS created_at
ORDER BY s.severity DESC
LIMIT $k
"""


async def get_secrets_for_character(
    session: AsyncSession,
    *,
    character_id: str,
    k: int = 3,
) -> list[dict[str, Any]]:
    """Fetch the top-k secrets known by a character, ordered by severity descending.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        k: Maximum number of secrets to return.

    Returns:
        List of secret property dicts ordered by severity descending.
    """
    result = await session.run(
        CYPHER_GET_SECRETS_FOR_CHARACTER,
        character_id=character_id,
        k=k,
    )
    return cast(
        list[dict[str, Any]],
        [dict(record) async for record in result],
    )
