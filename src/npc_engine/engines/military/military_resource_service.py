"""
Module: military_resource_service
Layer: engines
Purpose: Resource yield — for each faction controlling a producing location, credit
         treasury per tick and decrement ResourceNode depletion until exhausted.
Does NOT: call LLMs, resolve battles, or manage CONTROLS/OCCUPIES edges.
Dependencies injected: AsyncSession (via process_resource_yield).
Used by: npc_engine.engines.military.military_engine
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncSession
from pydantic import BaseModel

from npc_engine.graph.military_queries import get_faction_resource_nodes
from npc_engine.graph.military_control_writer import add_faction_treasury, set_resource_depletion

_LOGGER = logging.getLogger(__name__)

DEPLETION_PER_TICK = 1
MIN_DEPLETION = 0


class ResourceYieldResult(BaseModel):
    """Summary of resource yield for one faction in a single tick."""

    faction_id: str
    total_yield: int
    resources_depleted: int
    tick_id: int


async def process_resource_yield(
    session: AsyncSession,
    *,
    tick_id: int,
) -> list[ResourceYieldResult]:
    """Credit each controlling faction's treasury and decrement resource depletion.

    Fetches all (faction, resource_node) pairs where the faction controls the
    producing location and depletion > 0. Groups by faction, sums yield, makes
    one treasury update per faction, and decrements each resource node by
    DEPLETION_PER_TICK.

    Fallback: Neo4j unavailable → raises GraphUnavailableError (propagated to engine).

    Args:
        session: Active Neo4j async session.
        tick_id: Current game tick ID.

    Returns:
        List of ResourceYieldResult, one per faction that received resources.
    """
    rows = await get_faction_resource_nodes(session)
    if not rows:
        return []

    faction_totals, resource_depletions = _aggregate_yields(rows)

    results: list[ResourceYieldResult] = []
    for faction_id, total_yield in faction_totals.items():
        await add_faction_treasury(session, faction_id=faction_id, amount=total_yield)
        _LOGGER.info(
            "resource_yield",
            extra={"faction_id": faction_id, "amount": total_yield, "tick": tick_id},
        )
        results.append(
            ResourceYieldResult(
                faction_id=faction_id,
                total_yield=total_yield,
                resources_depleted=0,
                tick_id=tick_id,
            )
        )

    for resource_node_id, old_depletion in resource_depletions.items():
        new_depletion = max(MIN_DEPLETION, old_depletion - DEPLETION_PER_TICK)
        await set_resource_depletion(session, resource_node_id=resource_node_id, depletion=new_depletion)

    return results


def _aggregate_yields(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, int], dict[str, int]]:
    """Group rows by faction (summing yield) and collect resource depletion values.

    Args:
        rows: Each row has faction_id, resource_node_id, yield_per_tick, depletion.

    Returns:
        Tuple of (faction_totals, resource_depletions) dicts.
    """
    faction_totals: dict[str, int] = {}
    resource_depletions: dict[str, int] = {}

    for row in rows:
        faction_id: str = row["faction_id"]
        resource_node_id: str = row["resource_node_id"]
        yield_per_tick: int = int(row["yield_per_tick"])
        depletion: int = int(row["depletion"])

        if depletion <= 0:
            continue

        faction_totals[faction_id] = faction_totals.get(faction_id, 0) + yield_per_tick
        resource_depletions[resource_node_id] = depletion

    return faction_totals, resource_depletions
