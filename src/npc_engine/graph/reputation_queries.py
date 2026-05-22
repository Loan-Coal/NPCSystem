"""
Module: reputation_queries
Layer: graph
Purpose: Read-only Cypher accessors for HAS_REPUTATION_WITH edges.
Does NOT: execute write operations or open transactions.
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.reputation_service, npc_engine.retrieval.context_builder
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

CYPHER_GET_REPUTATION = """
MATCH (c:Character {id: $character_id})-[r:HAS_REPUTATION_WITH]->(f:Faction {id: $faction_id})
RETURN f.id AS faction_id, f.name AS faction_name, toInteger(r.standing) AS standing
"""

CYPHER_LIST_REPUTATIONS = """
MATCH (c:Character {id: $character_id})-[r:HAS_REPUTATION_WITH]->(f:Faction)
RETURN f.id AS faction_id, f.name AS faction_name, toInteger(r.standing) AS standing
ORDER BY r.standing DESC
"""

CYPHER_REPUTATION_CONTEXT = """
MATCH (npc:Character {id: $npc_id})-[:MEMBER_OF]->(f:Faction)
WHERE f.is_active = true
MATCH (player:Character {id: $player_id})-[r:HAS_REPUTATION_WITH]->(f)
WHERE abs(toInteger(r.standing)) >= $threshold
RETURN f.name AS faction_name, toInteger(r.standing) AS standing
"""

# ---------------------------------------------------------------------------
# Standing label
# ---------------------------------------------------------------------------

_LABELS: list[tuple[int, str]] = [
    (-50, "hostile"),
    (-20, "unfriendly"),
    (20, "neutral"),
    (50, "friendly"),
    (101, "allied"),
]


def _standing_label(standing: int) -> str:
    for threshold, label in _LABELS:
        if standing < threshold:
            return label
    return "allied"


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def get_reputation(
    session: AsyncSession,
    *,
    character_id: str,
    faction_id: str,
) -> dict[str, Any] | None:
    """Fetch a single HAS_REPUTATION_WITH edge by character and faction ID.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        faction_id: ID of the faction node.

    Returns:
        Dict with ``faction_id``, ``faction_name``, and ``standing``, or None if absent.
    """
    result = await session.run(
        CYPHER_GET_REPUTATION,
        character_id=character_id,
        faction_id=faction_id,
    )
    record = await result.single()
    await result.consume()
    if record is None:
        return None
    return cast(dict[str, Any], dict(record))


async def list_reputations(
    session: AsyncSession,
    *,
    character_id: str,
) -> list[dict[str, Any]]:
    """Fetch all HAS_REPUTATION_WITH edges for a character, ordered by standing descending.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.

    Returns:
        List of dicts with ``faction_id``, ``faction_name``, and ``standing``.
    """
    result = await session.run(CYPHER_LIST_REPUTATIONS, character_id=character_id)
    try:
        return cast(
            list[dict[str, Any]],
            [dict(record) async for record in result],
        )
    finally:
        await result.consume()


async def get_reputation_context_for_npc(
    session: AsyncSession,
    *,
    npc_id: str,
    player_id: str,
    threshold: int,
) -> list[dict[str, Any]]:
    """Fetch player reputation lines relevant to the NPC's faction memberships.

    Looks up which active factions the NPC belongs to, then returns the player's
    standing toward each of those factions where |standing| >= threshold.

    Args:
        session: Active Neo4j async session.
        npc_id: ID of the NPC character node.
        player_id: ID of the player character node.
        threshold: Minimum absolute standing value to include (e.g. 20).

    Returns:
        List of dicts with ``faction_name``, ``standing``, and ``label``.
    """
    result = await session.run(
        CYPHER_REPUTATION_CONTEXT,
        npc_id=npc_id,
        player_id=player_id,
        threshold=threshold,
    )
    try:
        rows = [dict(record) async for record in result]
    finally:
        await result.consume()
    return cast(
        list[dict[str, Any]],
        [
            {
                "faction_name": row["faction_name"],
                "standing": int(row["standing"]),
                "label": _standing_label(int(row["standing"])),
            }
            for row in rows
        ],
    )
