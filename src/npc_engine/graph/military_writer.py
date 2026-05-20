"""
Module: military_writer
Layer: graph
Purpose: Write operations for Army, ResourceNode, and OCCUPIES/COMMANDS/PRODUCES
         relationships (Phase 7.4 Strategy/4X).
Does NOT: read graph state beyond what MERGE requires, call LLMs, or import engine code.
Dependencies injected: None (pure Cypher, session passed per call).
Used by: npc_engine.engines.military.military_engine
"""

from __future__ import annotations

import json
import uuid

from neo4j import AsyncSession

_COMPOSITION_KEYS = frozenset({"infantry", "cavalry", "siege"})


def _validate_composition(composition: dict) -> str:
    """Validate and serialise an army composition dict to JSON.

    Args:
        composition: Must have exactly the keys infantry, cavalry, siege,
                     all with int values.

    Returns:
        JSON string of the validated composition.

    Raises:
        ValueError: If required keys are missing or values are not ints.
    """
    missing = _COMPOSITION_KEYS - composition.keys()
    if missing:
        raise ValueError(f"Army composition missing required keys: {missing}")
    for key in _COMPOSITION_KEYS:
        if not isinstance(composition[key], int):
            raise ValueError(
                f"Army composition key '{key}' must be int, got {type(composition[key]).__name__}"
            )
    return json.dumps({k: composition[k] for k in sorted(_COMPOSITION_KEYS)})


async def create_army(
    session: AsyncSession,
    *,
    faction_id: str,
    strength: int,
    location_id: str,
    composition: dict,
) -> str:
    """Create an Army node and place it at a location via OCCUPIES.

    Args:
        session: Active Neo4j async session.
        faction_id: Owning faction.
        strength: Initial army strength.
        location_id: Starting location.
        composition: Dict with keys infantry, cavalry, siege (all int).

    Returns:
        The generated army ID.

    Raises:
        ValueError: If composition is invalid.
    """
    composition_json = _validate_composition(composition)
    army_id = str(uuid.uuid4())
    await session.run(
        """
        MATCH (loc:Location {id: $location_id})
        CREATE (a:Army {
            id: $army_id,
            faction_id: $faction_id,
            strength: $strength,
            current_location_id: $location_id,
            composition: $composition
        })
        CREATE (a)-[:OCCUPIES {since_tick: 0}]->(loc)
        """,
        army_id=army_id,
        faction_id=faction_id,
        strength=strength,
        location_id=location_id,
        composition=composition_json,
    )
    return army_id


async def create_resource_node(
    session: AsyncSession,
    *,
    kind: str,
    yield_per_tick: int,
    depletion: int,
) -> str:
    """Create a ResourceNode.

    Args:
        session: Active Neo4j async session.
        kind: Resource category (gold / iron / grain / mana).
        yield_per_tick: Units produced per tick.
        depletion: Initial depletion level (0–100).

    Returns:
        The generated resource node ID.
    """
    node_id = str(uuid.uuid4())
    await session.run(
        """
        CREATE (r:ResourceNode {
            id: $node_id,
            kind: $kind,
            yield_per_tick: $yield_per_tick,
            depletion: $depletion
        })
        """,
        node_id=node_id,
        kind=kind,
        yield_per_tick=yield_per_tick,
        depletion=max(0, min(100, depletion)),
    )
    return node_id


async def link_resource_node(
    session: AsyncSession,
    *,
    location_id: str,
    resource_node_id: str,
) -> None:
    """Link a ResourceNode to a location via PRODUCES.

    Args:
        session: Active Neo4j async session.
        location_id: ID of the producing location.
        resource_node_id: ID of the ResourceNode.
    """
    await session.run(
        """
        MATCH (loc:Location {id: $location_id})
        MATCH (r:ResourceNode {id: $resource_node_id})
        MERGE (loc)-[:PRODUCES]->(r)
        """,
        location_id=location_id,
        resource_node_id=resource_node_id,
    )


async def move_army(
    session: AsyncSession,
    *,
    army_id: str,
    new_location_id: str,
    tick: int,
) -> None:
    """Move an army to a new location, removing the old OCCUPIES edge.

    Args:
        session: Active Neo4j async session.
        army_id: ID of the army to move.
        new_location_id: Destination location ID.
        tick: Current tick (stored on the new OCCUPIES edge).
    """
    await session.run(
        """
        MATCH (a:Army {id: $army_id})-[old:OCCUPIES]->()
        DELETE old
        WITH a
        MATCH (loc:Location {id: $new_location_id})
        CREATE (a)-[:OCCUPIES {since_tick: $tick}]->(loc)
        SET a.current_location_id = $new_location_id
        """,
        army_id=army_id,
        new_location_id=new_location_id,
        tick=tick,
    )


async def set_army_strength(
    session: AsyncSession,
    *,
    army_id: str,
    strength: int,
) -> None:
    """Update the strength of an army.

    Args:
        session: Active Neo4j async session.
        army_id: ID of the army.
        strength: New strength value.
    """
    await session.run(
        "MATCH (a:Army {id: $army_id}) SET a.strength = $strength",
        army_id=army_id,
        strength=strength,
    )


async def link_army_to_commander(
    session: AsyncSession,
    *,
    character_id: str,
    army_id: str,
) -> None:
    """Create a COMMANDS relationship from a character to an army.

    Uses MERGE so repeated calls are idempotent.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the commanding character.
        army_id: ID of the army.
    """
    await session.run(
        """
        MATCH (c:Character {id: $character_id})
        MATCH (a:Army {id: $army_id})
        MERGE (c)-[:COMMANDS]->(a)
        """,
        character_id=character_id,
        army_id=army_id,
    )
