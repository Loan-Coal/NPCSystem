"""
Module: faction_history_service
Layer: graph
Purpose: Append-only log of faction standing changes via FactionStandingEvent nodes.
Does NOT: modify STANDS_WITH edges or implement faction logic.
Dependencies: graph.faction_history_queries
Dependencies injected: AsyncSession.
Used by: npc_engine.engines.faction_politics.faction_politics_engine
"""

from __future__ import annotations

import uuid
from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.faction.faction_history_queries import (
    CYPHER_CREATE_FACTION_STANDING_EVENT,
    get_raw_trend_rows,
    get_standing_history,
)


async def record_standing_change(
    session: AsyncSession,
    *,
    src_faction_id: str,
    dst_faction_id: str,
    delta: int,
    new_standing: int,
    tick: int,
    cause_event_id: str | None = None,
    cause_rule_id: str | None = None,
) -> str:
    """Append a FactionStandingEvent node recording a standing change.

    Args:
        session: Active Neo4j async session.
        src_faction_id: Faction whose standing toward dst changed.
        dst_faction_id: Faction toward which the standing changed.
        delta: Signed magnitude of the change.
        new_standing: Standing value after the change.
        tick: Game tick at which the change occurred.
        cause_event_id: Optional Event node ID that triggered the change.
        cause_rule_id: Optional rule identifier that caused the change.

    Returns:
        ID of the newly created FactionStandingEvent node.
    """
    event_id = str(uuid.uuid4())
    await session.run(
        CYPHER_CREATE_FACTION_STANDING_EVENT,
        id=event_id,
        src_faction_id=src_faction_id,
        dst_faction_id=dst_faction_id,
        delta=delta,
        new_standing=new_standing,
        tick_id=tick,
        cause_event_id=cause_event_id,
        cause_rule_id=cause_rule_id,
    )
    return event_id


async def get_standing_history_svc(
    session: AsyncSession,
    src_faction_id: str,
    dst_faction_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return recent standing-change events between two factions.

    Args:
        session: Active Neo4j async session.
        src_faction_id: Source faction ID.
        dst_faction_id: Destination faction ID.
        limit: Maximum number of events to return.

    Returns:
        List of event dicts ordered by tick descending.
    """
    return await get_standing_history(
        session,
        src_faction_id=src_faction_id,
        dst_faction_id=dst_faction_id,
        limit=limit,
    )


async def get_standing_trend(
    session: AsyncSession,
    src_faction_id: str,
    dst_faction_id: str,
    window_ticks: int = 100,
    current_tick: int = 0,
) -> float:
    """Compute the trajectory of standing changes as a least-squares slope.

    A positive return value indicates improving relations; negative means worsening.
    Returns 0.0 when fewer than 2 data points exist in the window.

    Args:
        session: Active Neo4j async session.
        src_faction_id: Source faction ID.
        dst_faction_id: Destination faction ID.
        window_ticks: How many ticks back to include.
        current_tick: Reference tick (defaults to 0 for absolute window).

    Returns:
        Float slope of delta values over time (units: standing-change per tick).
    """
    min_tick = max(0, current_tick - window_ticks)
    rows = await get_raw_trend_rows(
        session,
        src_faction_id=src_faction_id,
        dst_faction_id=dst_faction_id,
        min_tick=min_tick,
    )
    if len(rows) < 2:
        return 0.0
    return _least_squares_slope([(r["tick_id"], r["delta"]) for r in rows])


def _least_squares_slope(points: list[tuple[int, int]]) -> float:
    """Return the least-squares regression slope for (x, y) pairs.

    Args:
        points: List of (tick_id, delta) integer pairs. Must have >= 2 elements.

    Returns:
        Slope as a float.
    """
    n = len(points)
    sum_x = sum(x for x, _ in points)
    sum_y = sum(y for _, y in points)
    sum_xx = sum(x * x for x, _ in points)
    sum_xy = sum(x * y for x, y in points)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom
