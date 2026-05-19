"""
Module: military_queries
Layer: graph
Purpose: Read-only Cypher queries for Army, ResourceNode, and territorial
         control (Phase 7.4 Strategy/4X).
Does NOT: write to the graph, call LLMs, or import engine-layer code.
Dependencies injected: None (pure Cypher, session passed per call).
Used by: npc_engine.engines.military.military_engine
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession


async def get_armies_for_faction(
    session: AsyncSession,
    faction_id: str,
) -> list[dict[str, Any]]:
    """Fetch all armies belonging to a faction.

    Args:
        session: Active Neo4j async session.
        faction_id: ID of the faction.

    Returns:
        List of dicts: army_id, strength, current_location_id, composition.
    """
    result = await session.run(
        """
        MATCH (a:Army {faction_id: $faction_id})
        RETURN a.id AS army_id,
               a.strength AS strength,
               a.current_location_id AS current_location_id,
               a.composition AS composition
        """,
        faction_id=faction_id,
    )
    return [dict(r) async for r in result]


async def get_army_at_location(
    session: AsyncSession,
    location_id: str,
) -> list[dict[str, Any]]:
    """Fetch all armies currently occupying a location.

    Args:
        session: Active Neo4j async session.
        location_id: ID of the location.

    Returns:
        List of dicts: army_id, faction_id, strength, since_tick.
    """
    result = await session.run(
        """
        MATCH (a:Army)-[occ:OCCUPIES]->(loc:Location {id: $location_id})
        RETURN a.id AS army_id,
               a.faction_id AS faction_id,
               a.strength AS strength,
               occ.since_tick AS since_tick
        """,
        location_id=location_id,
    )
    return [dict(r) async for r in result]


async def get_resource_nodes_at_location(
    session: AsyncSession,
    location_id: str,
) -> list[dict[str, Any]]:
    """Fetch all ResourceNode nodes linked to a location via PRODUCES.

    Args:
        session: Active Neo4j async session.
        location_id: ID of the location.

    Returns:
        List of dicts: resource_node_id, kind, yield_per_tick, depletion.
    """
    result = await session.run(
        """
        MATCH (loc:Location {id: $location_id})-[:PRODUCES]->(r:ResourceNode)
        RETURN r.id AS resource_node_id,
               r.kind AS kind,
               r.yield_per_tick AS yield_per_tick,
               r.depletion AS depletion
        """,
        location_id=location_id,
    )
    return [dict(r) async for r in result]


async def get_controlled_locations(
    session: AsyncSession,
    faction_id: str,
) -> list[dict[str, Any]]:
    """Fetch all locations controlled by a faction.

    Args:
        session: Active Neo4j async session.
        faction_id: ID of the faction.

    Returns:
        List of dicts: location_id, control_strength, contested_by_faction_id.
    """
    result = await session.run(
        """
        MATCH (f:Faction {id: $faction_id})-[ctrl:CONTROLS]->(loc:Location)
        RETURN loc.id AS location_id,
               ctrl.control_strength AS control_strength,
               ctrl.contested_by_faction_id AS contested_by_faction_id
        """,
        faction_id=faction_id,
    )
    return [dict(r) async for r in result]


async def get_armies_in_conflict(
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """Find locations that have armies from at least two different factions.

    Args:
        session: Active Neo4j async session.

    Returns:
        List of dicts: location_id, faction_ids (list), army_count.
    """
    result = await session.run(
        """
        MATCH (a:Army)-[:OCCUPIES]->(loc:Location)
        WITH loc, collect(DISTINCT a.faction_id) AS faction_ids, count(a) AS army_count
        WHERE size(faction_ids) >= 2
        RETURN loc.id AS location_id,
               faction_ids,
               army_count
        """
    )
    return [dict(r) async for r in result]
