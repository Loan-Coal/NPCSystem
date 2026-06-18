"""
Module: pledge_violation_service
Layer: graph
Purpose: Detect active pledge violations by querying WITNESSED and PARTICIPATED_IN
         edges since sworn_at_tick, then breaking violating pledges and emitting
         high-severity EVENT nodes.
Does NOT: create pledges, expire pledges, call LLMs, or orchestrate scheduling.
Dependencies injected: AsyncSession.
Dependencies: graph.pledge_queries, graph.pledge_service (break_pledge only)
Used by: npc_engine.engines.oath.oath_engine
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from neo4j import AsyncSession

from npc_engine.graph.pledge_queries import (
    get_active_pledges_for_pledger,
    get_participated_violations,
    get_witnessed_violations,
)
from npc_engine.graph.pledge_service import break_pledge

_logger = logging.getLogger(__name__)

_VIOLATION_EVENT_SEVERITY = 90
_VIOLATION_EVENT_LOCATION = "world"

# action_types on WITNESSED edges that violate each pledge type
_VIOLATION_ACTIONS: dict[str, list[str]] = {
    "protect": ["attack", "harm", "kill", "betray"],
    "fealty": ["betray", "defect", "desert", "abandon", "disobey"],
    "serve": ["betray", "abandon", "desert", "disobey", "defect"],
    "kill": ["protect", "aid", "heal", "shelter", "defend"],
    "vendetta": ["reconcile", "forgive", "aid", "protect", "defend"],
    "marry": ["betray", "abandon", "desert"],
    "mentor": ["harm", "abandon", "betray"],
}

# PARTICIPATED_IN roles that violate each pledge type
_VIOLATION_ROLES: dict[str, list[str]] = {
    "protect": ["aggressor", "attacker", "betrayer"],
    "fealty": ["deserter", "betrayer", "rebel"],
    "serve": ["deserter", "betrayer", "rebel"],
    "kill": ["protector", "defender", "healer"],
    "vendetta": ["peacemaker", "ally", "protector"],
    "marry": ["betrayer", "deserter"],
    "mentor": ["aggressor", "abandoner"],
}

_CYPHER_WRITE_VIOLATION_EVENT = """
MERGE (e:Event {id: $event_id})
SET e.event_type          = 'pledge_violation',
    e.summary             = $summary,
    e.severity            = $severity,
    e.location_id         = $location_id,
    e.occurred_at         = $occurred_at,
    e.tick_id             = $tick_id,
    e.is_public           = true,
    e.producer            = 'oath_engine',
    e.origin_engine       = 'oath_engine',
    e.schema_version      = '1.0',
    e.src_character_id    = $src_character_id,
    e.last_graph_updated_at = $last_graph_updated_at
"""


async def check_pledge_violations(
    session: AsyncSession,
    *,
    pledger_id: str,
    tick: int,
) -> list[dict[str, Any]]:
    """Detect active pledges that have been broken since they were sworn.

    For each active pledge, queries WITNESSED edges (pledger as subject) and
    PARTICIPATED_IN edges since sworn_at_tick. Calls break_pledge and emits a
    high-severity EVENT for each violation found. Each pledge is broken at most once
    per call even if both checks fire.

    Fallback: Neo4j unavailable → raises GraphUnavailableError (caller handles).

    Args:
        session: Active Neo4j async session.
        pledger_id: ID of the character whose pledges to check.
        tick: Current game tick (used for event timestamps).

    Returns:
        List of pledge dicts for pledges that were violated (and broken) this call.
    """
    pledges = await get_active_pledges_for_pledger(session, pledger_id=pledger_id)
    violated: list[dict[str, Any]] = []

    for pledge in pledges:
        pledge_type: str = pledge["pledge_type"]
        sworn_at: int = int(pledge["sworn_at_tick"])

        action_types = _VIOLATION_ACTIONS.get(pledge_type, [])
        roles = _VIOLATION_ROLES.get(pledge_type, [])

        witnessed = await get_witnessed_violations(
            session,
            pledger_id=pledger_id,
            since_tick=sworn_at,
            action_types=action_types,
        )
        participated = await get_participated_violations(
            session,
            pledger_id=pledger_id,
            since_tick=sworn_at,
            roles=roles,
        )

        if not witnessed and not participated:
            continue

        _logger.warning(
            "pledge_violation_detected",
            extra={
                "pledger_id": pledger_id,
                "pledgee_id": pledge["pledgee_id"],
                "pledge_type": pledge_type,
                "tick": tick,
            },
        )
        await break_pledge(
            session,
            pledger_id=pledger_id,
            pledgee_id=pledge["pledgee_id"],
            pledge_type=pledge_type,
            tick=tick,
        )
        await _emit_violation_event(session, pledger_id=pledger_id, pledge=pledge, tick=tick)
        violated.append(pledge)

    return violated


async def _emit_violation_event(
    session: AsyncSession,
    *,
    pledger_id: str,
    pledge: dict[str, Any],
    tick: int,
) -> None:
    """Write a high-severity Event node recording the pledge violation.

    Args:
        session: Active Neo4j async session.
        pledger_id: ID of the character who broke the pledge.
        pledge: Pledge dict containing pledgee_id, pledge_type, severity.
        tick: Current game tick.
    """
    event_id = f"violation_{pledger_id}_{pledge['pledge_type']}_{tick}_{uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    summary = (
        f"{pledger_id} violated {pledge['pledge_type']} pledge "
        f"to {pledge['pledgee_id']} at tick {tick}"
    )
    await session.run(
        _CYPHER_WRITE_VIOLATION_EVENT,
        event_id=event_id,
        summary=summary,
        severity=_VIOLATION_EVENT_SEVERITY,
        location_id=_VIOLATION_EVENT_LOCATION,
        occurred_at=now,
        tick_id=tick,
        src_character_id=pledger_id,
        last_graph_updated_at=now,
    )
