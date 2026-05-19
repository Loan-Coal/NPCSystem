"""
Module: witnessed_service
Layer: graph
Purpose: Functions for recording and querying WITNESSED edges (character observation records).
Does NOT: implement business logic, validate request payloads, or call LLMs.
Dependencies: graph.witnessed_queries
Dependencies injected: AsyncSession.
Used by: npc_engine.engines.events.event_handler, npc_engine.engines.gossip.knowledge_propagator,
         npc_engine.api.routes.witnessed
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.witnessed_queries import (
    CYPHER_CREATE_WITNESSED,
    CYPHER_MARK_DISCLOSED,
    get_undisclosed_witnesses,
    get_witnessed_by,
    get_witnesses_of_event,
)


async def record_witness(
    session: AsyncSession,
    *,
    witness_id: str,
    subject_id: str,
    event_id: str,
    action_type: str,
    tick: int,
    clarity: int,
    interpretation: str,
) -> None:
    """Create a WITNESSED edge from witness to subject for a given event.

    Args:
        session: Active Neo4j async session.
        witness_id: ID of the observing character.
        subject_id: ID of the character being observed.
        event_id: ID of the Event node this observation relates to.
        action_type: Description of the action observed (e.g. "stole", "helped").
        tick: Game tick at which the observation occurred.
        clarity: How clearly the witness observed (0–100); higher means more accurate recall.
        interpretation: The witness's biased reading of the action.
    """
    await session.run(
        CYPHER_CREATE_WITNESSED,
        witness_id=witness_id,
        subject_id=subject_id,
        event_id=event_id,
        action_type=action_type,
        witnessed_at_tick=tick,
        clarity=clarity,
        interpretation=interpretation,
    )


async def get_witnesses_of_event_svc(
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
    return await get_witnesses_of_event(session, event_id=event_id)


async def get_witnessed_by_svc(
    session: AsyncSession,
    *,
    subject_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return all WITNESSED edges pointing at subject_id.

    Args:
        session: Active Neo4j async session.
        subject_id: ID of the character being observed.
        limit: Maximum number of records to return.

    Returns:
        List of witness records ordered by most recent first.
    """
    return await get_witnessed_by(session, subject_id=subject_id, limit=limit)


async def get_undisclosed_witnesses_svc(
    session: AsyncSession,
    *,
    npc_id: str,
) -> list[dict[str, Any]]:
    """Return WITNESSED edges for npc_id where disclosed=False.

    Args:
        session: Active Neo4j async session.
        npc_id: ID of the witness character.

    Returns:
        List of undisclosed witness records.
    """
    return await get_undisclosed_witnesses(session, npc_id=npc_id)


async def mark_disclosed(
    session: AsyncSession,
    *,
    witness_id: str,
    subject_id: str,
    event_id: str,
) -> None:
    """Set disclosed=True on a WITNESSED edge.

    Args:
        session: Active Neo4j async session.
        witness_id: ID of the witness character.
        subject_id: ID of the subject character.
        event_id: ID of the event the edge relates to.
    """
    await session.run(
        CYPHER_MARK_DISCLOSED,
        witness_id=witness_id,
        subject_id=subject_id,
        event_id=event_id,
    )
