"""
Module: reputation_writer
Layer: graph
Purpose: Cypher mutation functions for HAS_REPUTATION_WITH edges between Character and Faction.
Does NOT: manage transaction lifecycle or execute queries directly on AsyncSession.
Dependencies injected: AsyncTransaction (via caller).
Used by: npc_engine.graph.reputation.reputation_service
"""

from __future__ import annotations

from neo4j import AsyncTransaction

from npc_engine.utils.errors import ReputationNotFoundError

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

CYPHER_SET_REPUTATION = """
MATCH (c:Character {id: $character_id})
MATCH (f:Faction {id: $faction_id})
MERGE (c)-[r:HAS_REPUTATION_WITH]->(f)
SET r.standing = $standing, r.last_changed_at = datetime()
RETURN r.standing AS standing
"""

CYPHER_GET_REPUTATION_STANDING = """
MATCH (c:Character {id: $character_id})-[r:HAS_REPUTATION_WITH]->(f:Faction {id: $faction_id})
RETURN toInteger(r.standing) AS standing
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MIN_STANDING = -100
_MAX_STANDING = 100


def _clamp(value: int) -> int:
    return max(_MIN_STANDING, min(_MAX_STANDING, value))


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def set_reputation(
    tx: AsyncTransaction,
    *,
    character_id: str,
    faction_id: str,
    standing: int,
) -> None:
    """Create or update a HAS_REPUTATION_WITH edge with a clamped standing value.

    Args:
        tx: Active Neo4j transaction.
        character_id: ID of the character node.
        faction_id: ID of the faction node.
        standing: Desired standing; clamped to [-100, 100] before write.

    Raises:
        ReputationNotFoundError: If the character or faction node does not exist.
    """
    clamped = _clamp(standing)
    result = await tx.run(
        CYPHER_SET_REPUTATION,
        character_id=character_id,
        faction_id=faction_id,
        standing=clamped,
    )
    record = await result.single()
    if record is None:
        raise ReputationNotFoundError(character_id=character_id, faction_id=faction_id)


async def adjust_reputation(
    tx: AsyncTransaction,
    *,
    character_id: str,
    faction_id: str,
    delta: int,
) -> int:
    """Apply a delta to an existing HAS_REPUTATION_WITH standing, clamping to [-100, 100].

    If no edge exists yet, the current standing is treated as 0.

    Args:
        tx: Active Neo4j transaction.
        character_id: ID of the character node.
        faction_id: ID of the faction node.
        delta: Integer change to apply (positive or negative).

    Returns:
        The new clamped standing value.

    Raises:
        ReputationNotFoundError: If the character or faction node does not exist.
    """
    read_result = await tx.run(
        CYPHER_GET_REPUTATION_STANDING,
        character_id=character_id,
        faction_id=faction_id,
    )
    read_record = await read_result.single()
    current = int(read_record["standing"]) if read_record is not None else 0
    new_standing = _clamp(current + delta)

    write_result = await tx.run(
        CYPHER_SET_REPUTATION,
        character_id=character_id,
        faction_id=faction_id,
        standing=new_standing,
    )
    write_record = await write_result.single()
    if write_record is None:
        raise ReputationNotFoundError(character_id=character_id, faction_id=faction_id)
    return new_standing


async def adjust_reputation_for_event(
    tx: AsyncTransaction,
    *,
    character_id: str,
    faction_id: str,
    delta: int,
) -> None:
    """Apply a reputation delta triggered by an in-game event.

    Thin wrapper around adjust_reputation for use by the event engine.

    Args:
        tx: Active Neo4j transaction.
        character_id: ID of the character node.
        faction_id: ID of the faction node.
        delta: Integer change to apply (positive or negative).

    Raises:
        ReputationNotFoundError: If the character or faction node does not exist.
    """
    await adjust_reputation(tx, character_id=character_id, faction_id=faction_id, delta=delta)
