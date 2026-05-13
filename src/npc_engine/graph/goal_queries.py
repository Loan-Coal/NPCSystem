"""
Module: goal_queries
Layer: graph
Purpose: Cypher string constants and read accessor for Goal nodes and PURSUES edges.
Does NOT: execute write operations or open transactions.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.goal_service
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

CYPHER_CREATE_GOAL = """
MERGE (g:Goal {id: $goal_id})
SET g.description = $description,
    g.urgency = $urgency,
    g.status = $status,
    g.created_at_game_time = $created_at_game_time,
    g.target_id = $target_id
WITH g
MATCH (c:Character {id: $character_id})
MERGE (c)-[:PURSUES]->(g)
RETURN g.id AS goal_id
"""

CYPHER_GET_GOALS_FOR_CHARACTER = """
MATCH (c:Character {id: $character_id})-[:PURSUES]->(g:Goal)
WHERE $status_filter = '' OR g.status = $status_filter
RETURN g.id AS id,
       g.description AS description,
       toInteger(g.urgency) AS urgency,
       g.status AS status,
       g.created_at_game_time AS created_at_game_time,
       g.target_id AS target_id
ORDER BY g.urgency DESC
LIMIT $k
"""

CYPHER_UPDATE_GOAL_STATUS = """
MATCH (g:Goal {id: $goal_id})
SET g.status = $status
"""

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def get_goals_for_character(
    session: AsyncSession,
    *,
    character_id: str,
    k: int,
    status_filter: str = "active",
) -> list[dict[str, Any]]:
    """Fetch top-k goals for a character ordered by urgency descending.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        k: Maximum number of goals to return.
        status_filter: When non-empty, only return goals with this status.
            Pass empty string to return all statuses.

    Returns:
        List of dicts with id, description, urgency, status,
        created_at_game_time, and target_id fields.
    """
    result = await session.run(
        CYPHER_GET_GOALS_FOR_CHARACTER,
        character_id=character_id,
        k=k,
        status_filter=status_filter,
    )
    return cast(
        list[dict[str, Any]],
        [dict(record) async for record in result],
    )
