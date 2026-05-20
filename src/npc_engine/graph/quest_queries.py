"""
Module: quest_queries
Layer: graph
Purpose: Read-only Neo4j queries for player quest state used by the retrieval layer.
Does NOT: mutate graph state or call LLM services.
Dependencies injected: AsyncSession (caller-managed).
Used by: retrieval.context_builder
"""

from __future__ import annotations

from neo4j import AsyncSession


async def get_active_quest_for_player(
    session: AsyncSession,
    player_id: str,
) -> dict | None:
    """Return the player's most recently created active quest node, or None.

    Fetches the single active quest for a player, ordered by creation time so
    that the most recently accepted quest is returned when multiple are active.

    The returned dict includes quest properties such as target_id, giver_id,
    and objectives, which the context scoring layer uses to boost relevance of
    quest-related items.

    Args:
        session: Active Neo4j async session.
        player_id: ID of the player character.

    Returns:
        Quest property dict, or None if the player has no active quest.
    """

    query = """
    MATCH (p:Character {id: $player_id})-[:HAS_QUEST]->(q:Quest {status: 'active'})
    RETURN q
    ORDER BY q.created_at DESC
    LIMIT 1
    """
    result = await session.run(query, player_id=player_id)
    records = await result.data()
    if not records:
        return None
    return dict(records[0]["q"])
