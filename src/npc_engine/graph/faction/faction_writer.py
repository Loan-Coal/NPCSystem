"""
Module: faction_writer
Layer: graph
Purpose: Cypher mutation functions for Faction nodes and their edges.
Does NOT: manage transaction lifecycle or execute queries directly on AsyncSession.
Dependencies injected: AsyncTransaction (via caller).
Used by: npc_engine.graph.faction.faction_service
"""

from __future__ import annotations

from pydantic import BaseModel
from neo4j import AsyncTransaction

from npc_engine.utils.errors import FactionMembershipError, FactionNotFoundError

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

CYPHER_UPSERT_FACTION = """
MERGE (f:Faction {id: $id})
SET f += $properties,
    f.last_graph_updated_at = datetime()
"""

CYPHER_ADD_MEMBER = """
MATCH (c:Character {id: $character_id})
MATCH (f:Faction {id: $faction_id})
MERGE (c)-[r:MEMBER_OF]->(f)
ON CREATE SET r.joined_at = datetime()
SET r.role = $role, r.status = $status
RETURN r.role AS role
"""

CYPHER_REMOVE_MEMBER = """
MATCH (c:Character {id: $character_id})-[r:MEMBER_OF]->(f:Faction {id: $faction_id})
DELETE r
RETURN count(r) AS deleted
"""

CYPHER_SET_STANDING = """
MATCH (a:Faction {id: $src_id})
MATCH (b:Faction {id: $dst_id})
MERGE (a)-[r:STANDS_WITH]->(b)
SET r.standing = $standing,
    r.last_changed_at = datetime()
RETURN r.standing AS standing
"""

CYPHER_SET_CONTROLS = """
MATCH (f:Faction {id: $faction_id})
MATCH (l:Location {id: $location_id})
MERGE (f)-[:CONTROLS]->(l)
RETURN f.id AS faction_id
"""

CYPHER_REMOVE_CONTROLS = """
MATCH (f:Faction {id: $faction_id})-[r:CONTROLS]->(l:Location {id: $location_id})
DELETE r
RETURN count(r) AS deleted
"""

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def upsert_faction(tx: AsyncTransaction, faction: BaseModel) -> None:
    """Insert or update a Faction node idempotently.

    Args:
        tx: Active Neo4j transaction.
        faction: Pydantic model with an ``id`` field and serializable faction properties.
    """
    await tx.run(
        CYPHER_UPSERT_FACTION,
        id=faction.id,  # type: ignore[attr-defined]
        properties=faction.model_dump(mode="json"),
    )


async def add_member(
    tx: AsyncTransaction,
    *,
    character_id: str,
    faction_id: str,
    role: str,
    status: str,
) -> None:
    """Create or update a MEMBER_OF edge from a Character to a Faction.

    If the edge already exists, only ``role`` and ``status`` are updated;
    ``joined_at`` is preserved from the original creation.

    Args:
        tx: Active Neo4j transaction.
        character_id: ID of the character node.
        faction_id: ID of the faction node.
        role: Membership role (leader | officer | member | recruit).
        status: Membership status (active | exiled | deceased).

    Raises:
        FactionMembershipError: If either node is not found in the graph.
    """
    result = await tx.run(
        CYPHER_ADD_MEMBER,
        character_id=character_id,
        faction_id=faction_id,
        role=role,
        status=status,
    )
    record = await result.single()
    if record is None:
        raise FactionMembershipError(
            character_id=character_id,
            faction_id=faction_id,
            detail="Character or Faction node not found",
        )


async def remove_member(tx: AsyncTransaction, *, character_id: str, faction_id: str) -> None:
    """Delete a MEMBER_OF edge between a Character and a Faction.

    Args:
        tx: Active Neo4j transaction.
        character_id: ID of the character node.
        faction_id: ID of the faction node.

    Raises:
        FactionMembershipError: If no MEMBER_OF edge exists between the nodes.
    """
    result = await tx.run(
        CYPHER_REMOVE_MEMBER,
        character_id=character_id,
        faction_id=faction_id,
    )
    record = await result.single()
    if record is None:
        raise FactionMembershipError(
            character_id=character_id,
            faction_id=faction_id,
            detail="MEMBER_OF edge not found",
        )


async def set_standing(
    tx: AsyncTransaction,
    *,
    src_id: str,
    dst_id: str,
    standing: int,
) -> None:
    """Create or update a directed STANDS_WITH edge between two Faction nodes.

    Standings are stored as two independent directed edges; A's view of B
    is separate from B's view of A.

    Args:
        tx: Active Neo4j transaction.
        src_id: ID of the source faction node.
        dst_id: ID of the destination faction node.
        standing: Integer from -100 (at war) to 100 (allied).

    Raises:
        FactionNotFoundError: If either faction node does not exist.
    """
    result = await tx.run(
        CYPHER_SET_STANDING,
        src_id=src_id,
        dst_id=dst_id,
        standing=standing,
    )
    record = await result.single()
    if record is None:
        raise FactionNotFoundError(faction_id=src_id)


async def set_controls(tx: AsyncTransaction, *, faction_id: str, location_id: str) -> None:
    """Create a CONTROLS edge from a Faction to a Location.

    Args:
        tx: Active Neo4j transaction.
        faction_id: ID of the faction node.
        location_id: ID of the location node.

    Raises:
        FactionNotFoundError: If the faction or location node does not exist.
    """
    result = await tx.run(
        CYPHER_SET_CONTROLS,
        faction_id=faction_id,
        location_id=location_id,
    )
    record = await result.single()
    if record is None:
        raise FactionNotFoundError(faction_id=faction_id)


async def remove_controls(tx: AsyncTransaction, *, faction_id: str, location_id: str) -> None:
    """Delete a CONTROLS edge from a Faction to a Location.

    Args:
        tx: Active Neo4j transaction.
        faction_id: ID of the faction node.
        location_id: ID of the location node.

    Raises:
        FactionNotFoundError: If no CONTROLS edge exists.
    """
    result = await tx.run(
        CYPHER_REMOVE_CONTROLS,
        faction_id=faction_id,
        location_id=location_id,
    )
    record = await result.single()
    if record is None:
        raise FactionNotFoundError(faction_id=faction_id)
