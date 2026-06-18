"""
Module: schedule_writer
Layer: graph
Purpose: Cypher mutation functions for Schedule nodes and FOLLOWS_SCHEDULE edges.
Does NOT: manage transaction lifecycle or execute queries directly on AsyncSession.
Dependencies injected: AsyncTransaction (via caller).
Used by: npc_engine.graph.schedule_service
"""

from __future__ import annotations

from typing import Any
from neo4j import AsyncTransaction

from npc_engine.utils.errors import ScheduleAssignmentError, ScheduleNotFoundError

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

CYPHER_UPSERT_SCHEDULE = """
MERGE (s:Schedule {id: $id})
SET s += $properties,
    s.last_graph_updated_at = datetime()
RETURN s.id AS id
"""

CYPHER_ASSIGN_SCHEDULE = """
MATCH (c:Character {id: $character_id})
MATCH (s:Schedule {id: $schedule_id})
OPTIONAL MATCH (c)-[old:FOLLOWS_SCHEDULE]->()
DELETE old
MERGE (c)-[:FOLLOWS_SCHEDULE]->(s)
RETURN c.id AS character_id
"""

CYPHER_UNASSIGN_SCHEDULE = """
MATCH (c:Character {id: $character_id})-[r:FOLLOWS_SCHEDULE]->()
DELETE r
RETURN count(r) AS deleted
"""

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def upsert_schedule(tx: AsyncTransaction, *, schedule_id: str, properties: dict[str, Any]) -> None:
    """Insert or update a Schedule node idempotently.

    Args:
        tx: Active Neo4j transaction.
        schedule_id: Unique identifier for the schedule.
        properties: Dict of schedule field values to set.

    Raises:
        ScheduleNotFoundError: If the MERGE returns no record (unexpected).
    """
    result = await tx.run(CYPHER_UPSERT_SCHEDULE, id=schedule_id, properties=properties)
    record = await result.single()
    if record is None:
        raise ScheduleNotFoundError(schedule_id=schedule_id)


async def assign_schedule(
    tx: AsyncTransaction,
    *,
    character_id: str,
    schedule_id: str,
) -> None:
    """Assign a Schedule to a Character, replacing any existing FOLLOWS_SCHEDULE edge.

    The operation is atomic: the old edge (if any) is deleted and the new edge
    is created in the same transaction.

    Args:
        tx: Active Neo4j transaction.
        character_id: ID of the character node.
        schedule_id: ID of the schedule node.

    Raises:
        ScheduleAssignmentError: If the Character or Schedule node is not found.
    """
    result = await tx.run(
        CYPHER_ASSIGN_SCHEDULE,
        character_id=character_id,
        schedule_id=schedule_id,
    )
    record = await result.single()
    if record is None:
        raise ScheduleAssignmentError(
            character_id=character_id,
            schedule_id=schedule_id,
            detail="Character or Schedule node not found",
        )


async def unassign_schedule(tx: AsyncTransaction, *, character_id: str) -> None:
    """Remove the FOLLOWS_SCHEDULE edge from a Character.

    Args:
        tx: Active Neo4j transaction.
        character_id: ID of the character node.
    """
    await tx.run(CYPHER_UNASSIGN_SCHEDULE, character_id=character_id)
