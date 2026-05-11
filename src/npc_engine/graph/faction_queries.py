"""
Module: faction_queries
Layer: graph
Purpose: Read-only Cypher accessors for Faction nodes and their edges.
Does NOT: execute write operations or open transactions.
Dependencies injected: AsyncSession.
Used by: npc_engine.api.routes.factions, npc_engine.retrieval.context_builder
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

from npc_engine.graph.generic_graph_utils import to_native

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

CYPHER_GET_FACTION = """
MATCH (f:Faction {id: $faction_id})
RETURN properties(f) AS faction
"""

CYPHER_LIST_FACTIONS = """
MATCH (f:Faction)
RETURN properties(f) AS faction
ORDER BY f.name
"""

CYPHER_LIST_FACTIONS_ACTIVE = """
MATCH (f:Faction)
WHERE f.is_active = $is_active
RETURN properties(f) AS faction
ORDER BY f.name
"""

CYPHER_GET_FACTIONS_FOR_CHARACTER = """
MATCH (c:Character {id: $character_id})-[r:MEMBER_OF]->(f:Faction)
WHERE f.is_active = true
RETURN properties(f) AS faction, properties(r) AS membership
"""

CYPHER_GET_MEMBERS_OF_FACTION = """
MATCH (c:Character)-[r:MEMBER_OF]->(f:Faction {id: $faction_id})
WHERE c.is_active = true
RETURN properties(c) AS character, properties(r) AS membership
ORDER BY c.name
"""

CYPHER_GET_STANDING = """
MATCH (a:Faction {id: $src_id})-[r:STANDS_WITH]->(b:Faction {id: $dst_id})
RETURN r.standing AS standing
"""

CYPHER_LIST_STANDINGS = """
MATCH (a:Faction {id: $faction_id})-[r:STANDS_WITH]->(b:Faction)
RETURN properties(b) AS target, r.standing AS standing
ORDER BY r.standing DESC
"""

CYPHER_GET_CONTROLLED_LOCATIONS = """
MATCH (f:Faction {id: $faction_id})-[:CONTROLS]->(l:Location)
RETURN properties(l) AS location
ORDER BY l.name
"""

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def get_faction(session: AsyncSession, faction_id: str) -> dict[str, Any] | None:
    """Fetch a Faction node by ID.

    Args:
        session: Active Neo4j async session.
        faction_id: ID of the faction node to fetch.

    Returns:
        Dict of faction properties, or None if not found.
    """
    result = await session.run(CYPHER_GET_FACTION, faction_id=faction_id)
    record = await result.single()
    if record is None:
        return None
    return cast(dict[str, Any], to_native(record["faction"]))


async def list_factions(
    session: AsyncSession,
    is_active: bool | None = None,
) -> list[dict[str, Any]]:
    """List all Faction nodes, optionally filtered by active status.

    Args:
        session: Active Neo4j async session.
        is_active: If provided, filters to only active or inactive factions.

    Returns:
        List of faction property dicts ordered by name.
    """
    if is_active is None:
        result = await session.run(CYPHER_LIST_FACTIONS)
    else:
        result = await session.run(CYPHER_LIST_FACTIONS_ACTIVE, is_active=is_active)
    return cast(list[dict[str, Any]], [to_native(record["faction"]) async for record in result])


async def get_factions_for_character(
    session: AsyncSession,
    character_id: str,
) -> list[dict[str, Any]]:
    """Fetch all active factions a character belongs to, with membership details.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.

    Returns:
        List of dicts, each with ``faction`` (node properties) and
        ``membership`` (MEMBER_OF edge properties).
    """
    result = await session.run(CYPHER_GET_FACTIONS_FOR_CHARACTER, character_id=character_id)
    return cast(list[dict[str, Any]], [
        {
            "faction": to_native(record["faction"]),
            "membership": to_native(record["membership"]),
        }
        async for record in result
    ])


async def get_members_of_faction(
    session: AsyncSession,
    faction_id: str,
) -> list[dict[str, Any]]:
    """Fetch all active characters belonging to a faction, with membership details.

    Args:
        session: Active Neo4j async session.
        faction_id: ID of the faction node.

    Returns:
        List of dicts, each with ``character`` (node properties) and
        ``membership`` (MEMBER_OF edge properties), ordered by character name.
    """
    result = await session.run(CYPHER_GET_MEMBERS_OF_FACTION, faction_id=faction_id)
    return cast(list[dict[str, Any]], [
        {
            "character": to_native(record["character"]),
            "membership": to_native(record["membership"]),
        }
        async for record in result
    ])


async def get_standing(
    session: AsyncSession,
    src_id: str,
    dst_id: str,
) -> int | None:
    """Fetch the directed STANDS_WITH standing value from one faction toward another.

    Args:
        session: Active Neo4j async session.
        src_id: ID of the source faction.
        dst_id: ID of the destination faction.

    Returns:
        Integer standing (-100 to 100), or None if no edge exists.
    """
    result = await session.run(CYPHER_GET_STANDING, src_id=src_id, dst_id=dst_id)
    record = await result.single()
    if record is None:
        return None
    return int(record["standing"])


async def list_standings(
    session: AsyncSession,
    faction_id: str,
) -> list[dict[str, Any]]:
    """Fetch all directed STANDS_WITH edges from a faction, ordered by standing descending.

    Args:
        session: Active Neo4j async session.
        faction_id: ID of the source faction.

    Returns:
        List of dicts with ``target`` (faction properties) and ``standing`` (int).
    """
    result = await session.run(CYPHER_LIST_STANDINGS, faction_id=faction_id)
    return cast(list[dict[str, Any]], [
        {
            "target": to_native(record["target"]),
            "standing": int(record["standing"]),
        }
        async for record in result
    ])


async def get_controlled_locations(
    session: AsyncSession,
    faction_id: str,
) -> list[dict[str, Any]]:
    """Fetch all locations controlled by a faction.

    Args:
        session: Active Neo4j async session.
        faction_id: ID of the faction node.

    Returns:
        List of location property dicts, ordered by name.
    """
    result = await session.run(CYPHER_GET_CONTROLLED_LOCATIONS, faction_id=faction_id)
    return cast(list[dict[str, Any]], [to_native(record["location"]) async for record in result])
