"""
Module: quest_chain_queries
Layer: graph
Purpose: Cypher queries for UNLOCKS edge traversal — returns next quest IDs
    that are unlocked by a given quest and outcome, or by a specific player choice.
Dependencies: neo4j (AsyncSession).
Used by: npc_engine.engines.quest.quest_chain_resolver

Does NOT: call the LLM, import from engines, or implement business logic.
Dependencies injected: AsyncSession (per call).
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession


_logger = logging.getLogger(__name__)

_CYPHER_GET_UNLOCKED_QUESTS = """
MATCH (src:Quest {id: $quest_id})-[r:UNLOCKS]->(dst:Quest)
WHERE r.on_outcome = $outcome
RETURN dst.id AS next_quest_id
"""

_CYPHER_GET_CHOICE_UNLOCKED_QUEST = """
MATCH (src:Quest {id: $quest_id})-[r:UNLOCKS]->(dst:Quest)
WHERE r.on_choice_id = $choice_id
RETURN dst.id AS next_quest_id
LIMIT 1
"""


async def get_unlocked_quests(
    *,
    session: AsyncSession,
    quest_id: str,
    outcome: str,
) -> list[str]:
    """Return IDs of quests unlocked by quest_id when outcome matches.

    Queries the graph for outgoing UNLOCKS edges where ``r.on_outcome == outcome``
    and returns the destination quest IDs.

    Args:
        session: Active Neo4j async session.
        quest_id: Source quest node ID.
        outcome: Outcome string to match against UNLOCKS.on_outcome
            (e.g. ``"complete"``, ``"fail"``).

    Returns:
        List of next quest IDs (may be empty if no matching UNLOCKS edges exist).
    """
    result = await session.run(
        _CYPHER_GET_UNLOCKED_QUESTS,
        quest_id=quest_id,
        outcome=outcome,
    )
    records = [record["next_quest_id"] async for record in result]
    await result.consume()
    _logger.debug(
        "unlocked_quests_fetched",
        extra={"quest_id": quest_id, "outcome": outcome, "count": len(records)},
    )
    return records


async def get_choice_unlocked_quest(
    *,
    session: AsyncSession,
    quest_id: str,
    choice_id: str,
) -> str | None:
    """Return the quest ID unlocked by a specific player choice, or None.

    Queries the graph for an outgoing UNLOCKS edge where ``r.on_choice_id == choice_id``
    and returns the destination quest ID. LIMIT 1 is applied — only one branch should
    match a given choice_id; if none match, returns None (back-compat: null on_choice_id
    edges are not matched by this query).

    Args:
        session: Active Neo4j async session.
        quest_id: Source quest node ID.
        choice_id: Player choice ID to match against UNLOCKS.on_choice_id.

    Returns:
        Next quest ID if a matching UNLOCKS edge exists, otherwise None.
    """
    result = await session.run(
        _CYPHER_GET_CHOICE_UNLOCKED_QUEST,
        quest_id=quest_id,
        choice_id=choice_id,
    )
    record = await result.single()
    await result.consume()
    next_quest_id: str | None = record["next_quest_id"] if record else None
    _logger.debug(
        "choice_unlocked_quest_fetched",
        extra={"quest_id": quest_id, "choice_id": choice_id, "matched": next_quest_id is not None},
    )
    return next_quest_id
