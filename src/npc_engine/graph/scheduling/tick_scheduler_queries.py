"""
Module: tick_scheduler_queries
Layer: graph
Purpose: Cypher queries for SchedulerState tick-done tracking used by the local (non-distributed) scheduler path.
Does NOT: run engine handlers or manage leases.
Dependencies injected: AsyncSession (caller-managed).
Used by: scheduler.tick_scheduler
"""
from __future__ import annotations

from neo4j import AsyncSession

_CYPHER_TICK_DONE = """
MERGE (s:SchedulerState {id: $scheduler_id})
WITH s, coalesce(s[$key], []) AS completed
RETURN $tick_id IN completed AS done
"""

_CYPHER_MARK_TICK_DONE = """
MERGE (s:SchedulerState {id: $scheduler_id})
WITH s, coalesce(s[$key], []) AS completed
SET s[$key] = CASE
    WHEN $tick_id IN completed THEN completed
    ELSE completed + $tick_id
END
"""


async def is_tick_done(
    session: AsyncSession,
    scheduler_id: str,
    key: str,
    tick_id: int,
) -> bool:
    """Return True when tick_id is recorded in the SchedulerState node's completed list for key.

    Args:
        session: Active Neo4j async session.
        scheduler_id: Unique scheduler node ID.
        key: Property key on the SchedulerState node (e.g. 'gossip_ticks').
        tick_id: Tick ID to look up.

    Returns:
        True if tick_id is in the completed list; False otherwise.
    """
    result = await session.run(
        _CYPHER_TICK_DONE,
        scheduler_id=scheduler_id,
        key=key,
        tick_id=tick_id,
    )
    row = await result.single()
    return bool(row["done"]) if row is not None else False


async def mark_tick_done(
    session: AsyncSession,
    scheduler_id: str,
    key: str,
    tick_id: int,
) -> None:
    """Append tick_id to the SchedulerState node's completed list for key (idempotent).

    Args:
        session: Active Neo4j async session.
        scheduler_id: Unique scheduler node ID.
        key: Property key on the SchedulerState node.
        tick_id: Tick ID to record as done.
    """
    await session.run(
        _CYPHER_MARK_TICK_DONE,
        scheduler_id=scheduler_id,
        key=key,
        tick_id=tick_id,
    )
