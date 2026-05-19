"""
Module: witnessed_queries
Layer: graph
Purpose: Cypher query strings and read accessors for WITNESSED edges (character observation records).
Does NOT: execute business logic or validate payloads.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.witnessed_service
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Write queries
# ---------------------------------------------------------------------------

CYPHER_CREATE_WITNESSED = """
MATCH (witness:Character {id: $witness_id}), (subject:Character {id: $subject_id})
CREATE (witness)-[:WITNESSED {
    event_id:          $event_id,
    action_type:       $action_type,
    witnessed_at_tick: $witnessed_at_tick,
    clarity:           $clarity,
    interpretation:    $interpretation,
    disclosed:         false
}]->(subject)
"""

CYPHER_MARK_DISCLOSED = """
MATCH (witness:Character {id: $witness_id})-[e:WITNESSED {event_id: $event_id}]->(subject:Character {id: $subject_id})
SET e.disclosed = true
"""

# ---------------------------------------------------------------------------
# Read queries
# ---------------------------------------------------------------------------

CYPHER_GET_WITNESSES_OF_EVENT = """
MATCH (witness:Character)-[e:WITNESSED {event_id: $event_id}]->(subject:Character)
RETURN witness.id AS witness_id,
       witness.name AS witness_name,
       subject.id AS subject_id,
       subject.name AS subject_name,
       e.action_type AS action_type,
       toInteger(e.witnessed_at_tick) AS witnessed_at_tick,
       toInteger(e.clarity) AS clarity,
       e.interpretation AS interpretation,
       e.disclosed AS disclosed
"""

CYPHER_GET_WITNESSED_BY = """
MATCH (witness:Character)-[e:WITNESSED]->(subject:Character {id: $subject_id})
RETURN witness.id AS witness_id,
       witness.name AS witness_name,
       e.event_id AS event_id,
       e.action_type AS action_type,
       toInteger(e.witnessed_at_tick) AS witnessed_at_tick,
       toInteger(e.clarity) AS clarity,
       e.interpretation AS interpretation,
       e.disclosed AS disclosed
ORDER BY e.witnessed_at_tick DESC
LIMIT $limit
"""

CYPHER_GET_UNDISCLOSED_WITNESSES = """
MATCH (npc:Character {id: $npc_id})-[e:WITNESSED {disclosed: false}]->(subject:Character)
RETURN subject.id AS subject_id,
       subject.name AS subject_name,
       e.event_id AS event_id,
       e.action_type AS action_type,
       toInteger(e.witnessed_at_tick) AS witnessed_at_tick,
       toInteger(e.clarity) AS clarity,
       e.interpretation AS interpretation
"""


async def get_witnesses_of_event(
    session: AsyncSession,
    *,
    event_id: str,
) -> list[dict[str, Any]]:
    """Return all characters who witnessed a given event.

    Args:
        session: Active Neo4j async session.
        event_id: ID of the Event node.

    Returns:
        List of witness records for the event.
    """
    result = await session.run(CYPHER_GET_WITNESSES_OF_EVENT, event_id=event_id)
    return cast(list[dict[str, Any]], [dict(record) async for record in result])


async def get_witnessed_by(
    session: AsyncSession,
    *,
    subject_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return all WITNESSED edges pointing at subject_id (what others have seen them do).

    Args:
        session: Active Neo4j async session.
        subject_id: ID of the character being observed.
        limit: Maximum number of records to return.

    Returns:
        List of witness records ordered by most recent first.
    """
    result = await session.run(
        CYPHER_GET_WITNESSED_BY, subject_id=subject_id, limit=limit
    )
    return cast(list[dict[str, Any]], [dict(record) async for record in result])


async def get_undisclosed_witnesses(
    session: AsyncSession,
    *,
    npc_id: str,
) -> list[dict[str, Any]]:
    """Return WITNESSED edges for npc_id where disclosed=False (latent rumor sources).

    Args:
        session: Active Neo4j async session.
        npc_id: ID of the witness character.

    Returns:
        List of undisclosed witness records the NPC has not yet shared.
    """
    result = await session.run(CYPHER_GET_UNDISCLOSED_WITNESSES, npc_id=npc_id)
    return cast(list[dict[str, Any]], [dict(record) async for record in result])
