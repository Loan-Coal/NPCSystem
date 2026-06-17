"""
Module: quest_queries
Layer: graph
Purpose: Read-only Neo4j queries for player and NPC quest state used by the retrieval layer.
Does NOT: mutate graph state or call LLM services.
Dependencies injected: AsyncSession (caller-managed).
Used by: retrieval.context_builder
"""

from __future__ import annotations

from typing import Any
from neo4j import AsyncSession


async def get_active_quest_for_player(
    session: AsyncSession,
    player_id: str,
) -> dict[str, Any] | None:
    """Return the player's most recent accepted or in-progress quest state, or None.

    Queries QuestState nodes (the lifecycle state store) rather than Quest nodes,
    which may not have their status field updated by lifecycle transitions.

    Args:
        session: Active Neo4j async session.
        player_id: ID of the player character.

    Returns:
        Dict with QuestState fields (quest_id, title, status, objectives, etc.),
        or None if the player has no active quest.
    """
    query = """
    MATCH (qs:QuestState {player_id: $player_id})
    WHERE qs.status IN ['accepted', 'in_progress']
    RETURN qs
    ORDER BY qs.updated_at DESC
    LIMIT 1
    """
    result = await session.run(query, player_id=player_id)
    records = await result.data()
    if not records:
        return None
    return dict(records[0]["qs"])


async def get_offered_quests_for_npc(
    session: AsyncSession,
    npc_id: str,
) -> list[dict[str, Any]]:
    """Return quests the NPC has generated that are still in offered or accepted state.

    Used by the context builder to inject the NPC's offerable quest list so the
    NPC can reference it in dialogue without hallucinating.

    Args:
        session: Active Neo4j async session.
        npc_id: Character node ID of the NPC quest giver.

    Returns:
        List of dicts with id, description, quest_giver_id, status fields.
        Empty list if no matching quests exist.
    """
    query = """
    MATCH (c:Character {id: $npc_id})-[:HAS_QUEST]->(q:Quest)
    WHERE q.status IN ['offered', 'accepted', 'in_progress']
    RETURN q.id AS id, q.description AS description,
           q.quest_giver_id AS quest_giver_id, q.status AS status
    LIMIT 3
    """
    result = await session.run(query, npc_id=npc_id)
    records = await result.data()
    return [dict(r) for r in records]
