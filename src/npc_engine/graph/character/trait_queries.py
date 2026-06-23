"""
Module: trait_queries
Layer: graph
Purpose: Cypher queries for Trait nodes and HAS_TRAIT edges.
Does NOT: implement business logic or call LLMs.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.character.trait_service
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Write queries
# ---------------------------------------------------------------------------

CYPHER_MERGE_HAS_TRAIT = """
MATCH (c:Character {id: $character_id}), (t:Trait {id: $trait_id})
MERGE (c)-[e:HAS_TRAIT]->(t)
ON CREATE SET e.intensity = $intensity, e.is_secret = $is_secret
ON MATCH SET  e.intensity = $intensity, e.is_secret = $is_secret
"""

CYPHER_DELETE_HAS_TRAIT = """
MATCH (c:Character {id: $character_id})-[e:HAS_TRAIT]->(t:Trait {id: $trait_id})
DELETE e
"""

# ---------------------------------------------------------------------------
# Read queries
# ---------------------------------------------------------------------------

CYPHER_GET_TRAITS = """
MATCH (c:Character {id: $character_id})-[e:HAS_TRAIT]->(t:Trait)
RETURN t.id AS trait_id,
       t.name AS name,
       t.description AS description,
       toInteger(e.intensity) AS intensity,
       e.is_secret AS is_secret
ORDER BY e.intensity DESC
"""


async def get_traits(
    session: AsyncSession,
    *,
    character_id: str,
) -> list[dict[str, Any]]:
    """Fetch all traits for a character ordered by intensity descending.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node.

    Returns:
        List of trait dicts with trait_id, name, intensity, is_secret fields.
    """
    result = await session.run(CYPHER_GET_TRAITS, character_id=character_id)
    return cast(list[dict[str, Any]], [dict(record) async for record in result])
