"""
Module: military_control_writer
Layer: graph
Purpose: Write operations for territorial control (CONTROLS edges), faction treasury
         adjustments, and ResourceNode depletion updates (Phase 7.4 Strategy/4X).
Does NOT: manage Army or ResourceNode creation, call LLMs, or import engine code.
Dependencies injected: None (pure Cypher, session passed per call).
Used by: npc_engine.engines.military.military_battle_service,
         npc_engine.engines.military.military_resource_service
"""

from __future__ import annotations

from neo4j import AsyncSession

_CYPHER_SET_CONTROLS_LOCATION = """
MATCH (f:Faction {id: $faction_id}), (loc:Location {id: $location_id})
MERGE (f)-[ctrl:CONTROLS]->(loc)
SET ctrl.control_strength = $control_strength,
    ctrl.contested_by_faction_id = $contested_by
"""

_CYPHER_REMOVE_CONTROLS_LOCATION = """
MATCH (f:Faction {id: $faction_id})-[ctrl:CONTROLS]->(loc:Location {id: $location_id})
DELETE ctrl
"""

_CYPHER_ADD_FACTION_TREASURY = """
MATCH (f:Faction {id: $faction_id})
SET f.treasury = coalesce(f.treasury, 0) + $amount,
    f.last_graph_updated_at = datetime()
"""

_CYPHER_SET_RESOURCE_DEPLETION = """
MATCH (r:ResourceNode {id: $resource_node_id})
SET r.depletion = $depletion
"""


async def set_controls_location(
    session: AsyncSession,
    *,
    faction_id: str,
    location_id: str,
    control_strength: int,
    contested_by: str | None = None,
) -> None:
    """Upsert a CONTROLS edge from a faction to a location.

    Args:
        session: Active Neo4j async session.
        faction_id: ID of the controlling faction.
        location_id: ID of the location being controlled.
        control_strength: 0–100 strength of control.
        contested_by: Faction ID challenging control, or None.
    """
    await session.run(
        _CYPHER_SET_CONTROLS_LOCATION,
        faction_id=faction_id,
        location_id=location_id,
        control_strength=control_strength,
        contested_by=contested_by,
    )


async def remove_controls_location(
    session: AsyncSession,
    *,
    faction_id: str,
    location_id: str,
) -> None:
    """Delete a CONTROLS edge from a faction to a location.

    Args:
        session: Active Neo4j async session.
        faction_id: ID of the faction losing control.
        location_id: ID of the location.
    """
    await session.run(
        _CYPHER_REMOVE_CONTROLS_LOCATION,
        faction_id=faction_id,
        location_id=location_id,
    )


async def add_faction_treasury(
    session: AsyncSession,
    *,
    faction_id: str,
    amount: int,
) -> None:
    """Add (or subtract, if negative) amount to a faction's treasury.

    Args:
        session: Active Neo4j async session.
        faction_id: ID of the faction.
        amount: Amount to add (may be negative to deduct).
    """
    await session.run(
        _CYPHER_ADD_FACTION_TREASURY,
        faction_id=faction_id,
        amount=amount,
    )


async def set_resource_depletion(
    session: AsyncSession,
    *,
    resource_node_id: str,
    depletion: int,
) -> None:
    """Set the depletion level of a ResourceNode (0–100).

    Args:
        session: Active Neo4j async session.
        resource_node_id: ID of the ResourceNode.
        depletion: New depletion value (clamped to 0–100 by caller).
    """
    await session.run(
        _CYPHER_SET_RESOURCE_DEPLETION,
        resource_node_id=resource_node_id,
        depletion=depletion,
    )
