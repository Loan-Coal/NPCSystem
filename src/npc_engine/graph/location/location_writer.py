"""
Module: location_writer
Layer: graph
Purpose: Graph write operations for Location nodes and PART_OF containment edges.
Does NOT: open transactions, call LLM, or implement business logic.
Dependencies: neo4j AsyncSession, datetime
Dependencies injected: AsyncSession (per call — caller opens and commits transaction).
Used by: npc_engine.api.routes.locations, seeds/worlds seeders
"""

from __future__ import annotations

from datetime import datetime, timezone

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

_CYPHER_MERGE_PART_OF = """
MATCH (c:Location {id: $child_id}), (p:Location {id: $parent_id})
MERGE (c)-[r:PART_OF]->(p)
ON CREATE SET r.hierarchy_level = $level, r.established_at = $now
ON MATCH  SET r.hierarchy_level = $level
RETURN r
"""

_CYPHER_DELETE_PART_OF = """
MATCH (c:Location {id: $child_id})-[r:PART_OF]->(p:Location {id: $parent_id})
DELETE r
"""


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def write_part_of(
    session: AsyncSession,
    *,
    child_id: str,
    parent_id: str,
    hierarchy_level: int,
) -> None:
    """Create or update a PART_OF containment edge between two Location nodes.

    Uses MERGE semantics so repeated calls with the same (child_id, parent_id)
    pair are idempotent. The hierarchy_level is always updated on match.

    Args:
        session: Active Neo4j async session (caller owns transaction lifecycle).
        child_id: ID of the child Location node (the contained location).
        parent_id: ID of the parent Location node (the container).
        hierarchy_level: Depth level — 0=venue, 1=district, 2=city, 3=region,
            4=world.

    Raises:
        ValueError: If child_id equals parent_id (self-containment is invalid).
    """
    if child_id == parent_id:
        raise ValueError(
            f"A location cannot be PART_OF itself: {child_id!r}"
        )
    now = datetime.now(timezone.utc).isoformat()
    await session.run(
        _CYPHER_MERGE_PART_OF,
        child_id=child_id,
        parent_id=parent_id,
        level=hierarchy_level,
        now=now,
    )


async def delete_part_of(
    session: AsyncSession,
    *,
    child_id: str,
    parent_id: str,
) -> None:
    """Remove a PART_OF containment edge between two Location nodes.

    Safe to call even if the edge does not exist — no error is raised.

    Args:
        session: Active Neo4j async session (caller owns transaction lifecycle).
        child_id: ID of the child Location node.
        parent_id: ID of the parent Location node.
    """
    await session.run(
        _CYPHER_DELETE_PART_OF,
        child_id=child_id,
        parent_id=parent_id,
    )
