"""
Module: location_history_service
Layer: graph
Purpose: Functions for recording character location history via WAS_AT edges.
Does NOT: implement business logic, validate request payloads, or call LLMs.
Dependencies: graph.location_history_queries
Dependencies injected: AsyncSession.
Used by: npc_engine.engines.routine.routine_engine, npc_engine.api.routes.location_history
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.location.location_history_queries import (
    CYPHER_CREATE_WAS_AT,
    CYPHER_DELETE_OLD_WAS_AT,
    get_alibi_window,
    get_location_history,
)


async def record_departure(
    session: AsyncSession,
    *,
    character_id: str,
    location_id: str,
    arrived_at_tick: int,
    departed_at_tick: int,
    reason: str,
) -> None:
    """Archive a character's stay at a location as a WAS_AT edge.

    Should be called before overwriting the character's LOCATED_AT edge.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the departing character.
        location_id: ID of the location being left.
        arrived_at_tick: Tick when the character arrived at this location.
        departed_at_tick: Tick when the character is departing.
        reason: Why the character was at this location (e.g. "routine", "quest", "fled").
    """
    tick_duration = max(0, departed_at_tick - arrived_at_tick)
    await session.run(
        CYPHER_CREATE_WAS_AT,
        character_id=character_id,
        location_id=location_id,
        arrived_at_tick=arrived_at_tick,
        departed_at_tick=departed_at_tick,
        reason=reason,
        tick_duration=tick_duration,
    )


async def get_location_history_svc(
    session: AsyncSession,
    *,
    character_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return WAS_AT edges in reverse chronological order.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        limit: Maximum number of history records to return.

    Returns:
        List of location history dicts ordered by most recent departure first.
    """
    return await get_location_history(session, character_id=character_id, limit=limit)


async def get_alibi_window_svc(
    session: AsyncSession,
    *,
    character_id: str,
    from_tick: int,
    to_tick: int,
) -> list[dict[str, Any]]:
    """Return all locations a character was at during a tick window.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        from_tick: Start of the tick window (inclusive).
        to_tick: End of the tick window (inclusive).

    Returns:
        List of location records ordered by arrival tick ascending.
    """
    return await get_alibi_window(
        session, character_id=character_id, from_tick=from_tick, to_tick=to_tick
    )


async def prune_location_history(
    session: AsyncSession,
    *,
    character_id: str,
    older_than_ticks: int,
) -> int:
    """Remove WAS_AT edges older than a tick threshold.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character whose history to prune.
        older_than_ticks: Delete edges with departed_at_tick < this value.

    Returns:
        Number of WAS_AT edges deleted.
    """
    result = await session.run(
        CYPHER_DELETE_OLD_WAS_AT,
        character_id=character_id,
        older_than_tick=older_than_ticks,
    )
    record = await result.single()
    return int(record["deleted"]) if record else 0
