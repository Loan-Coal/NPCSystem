"""
Module: quest_node_service
Layer: graph
Purpose: Functions for creating Quest nodes and retrieving them by ID.
Does NOT: implement business logic, validate quest rules, or call LLMs.
Dependencies: graph.quest_node_queries
Dependencies injected: AsyncSession.
Used by: npc_engine.engines.quest_generation.quest_generation_engine
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.quest_node_queries import (
    CYPHER_CREATE_QUEST,
    CYPHER_GET_DRAFT_QUESTS,
    CYPHER_GET_QUEST,
    CYPHER_OFFER_QUEST,
)


async def create_quest(
    session: AsyncSession,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Create a Quest node and link it to the quest giver via HAS_QUEST edge.

    Args:
        session: Active Neo4j async session.
        payload: Dict with keys: quest_id, description, quest_giver_id, target_id,
            reward_id, success_condition, failure_condition, status, severity,
            created_at, completed_at.

    Returns:
        The payload dict echoed back with the confirmed quest_id.
    """
    tx = await session.begin_transaction()
    async with tx:
        result = await tx.run(
            CYPHER_CREATE_QUEST,
            quest_id=payload["quest_id"],
            description=payload["description"],
            quest_giver_id=payload["quest_giver_id"],
            target_id=payload.get("target_id"),
            reward_id=payload.get("reward_id"),
            success_condition=payload["success_condition"],
            failure_condition=payload.get("failure_condition"),
            status=payload["status"],
            severity=int(payload["severity"]),
            created_at=payload["created_at"],
            completed_at=payload.get("completed_at"),
            source=payload.get("source"),
        )
        await result.consume()
    return payload


async def get_draft_quests(
    session: AsyncSession,
    quest_giver_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return all Quest nodes with status='draft', optionally filtered by giver.

    Args:
        session: Active Neo4j async session.
        quest_giver_id: When provided, only return drafts for this character.

    Returns:
        List of quest property dicts ordered by created_at ascending.
    """
    result = await session.run(
        CYPHER_GET_DRAFT_QUESTS,
        quest_giver_id=quest_giver_id,
    )
    records = [dict(record) async for record in result]
    await result.consume()
    return records


async def offer_quest(
    session: AsyncSession,
    quest_id: str,
) -> dict[str, Any] | None:
    """Transition a draft quest to offered status.

    Only succeeds when the quest's current status is 'draft'. Returns None
    when no matching draft quest is found (quest does not exist or is not a draft).

    Args:
        session: Active Neo4j async session.
        quest_id: ID of the Quest node to offer.

    Returns:
        Dict with ``quest_id`` and ``status='offered'``, or None if not found/not a draft.
    """
    result = await session.run(CYPHER_OFFER_QUEST, quest_id=quest_id)
    records = [dict(record) async for record in result]
    await result.consume()
    return records[0] if records else None


async def get_quest(
    session: AsyncSession,
    quest_id: str,
) -> dict[str, Any] | None:
    """Retrieve a single Quest node by ID.

    Args:
        session: Active Neo4j async session.
        quest_id: ID of the Quest node to retrieve.

    Returns:
        Dict of quest properties, or None if no such quest exists.
    """
    result = await session.run(CYPHER_GET_QUEST, quest_id=quest_id)
    records = [dict(record) async for record in result]
    return records[0] if records else None
