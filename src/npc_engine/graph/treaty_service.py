"""
Module: treaty_service
Layer: graph
Purpose: Create, read, expire, and break Treaty nodes with mechanical condition checking.
Does NOT: call LLMs directly (LLM eval is delegated to the caller engine).
Dependencies injected: AsyncSession.
Dependencies: graph.treaty_queries
Used by: npc_engine.engines.treaty.treaty_engine, npc_engine.api.routes.treaties
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from neo4j import AsyncSession
from pydantic import BaseModel

from npc_engine.graph.treaty_queries import (
    CYPHER_CREATE_BOUND_BY,
    CYPHER_CREATE_TREATY,
    CYPHER_SET_TREATY_STATUS,
    get_active_treaties,
    get_expiring_treaties,
    get_treaty_conditions,
)


# ---------------------------------------------------------------------------
# Treaty condition model
# ---------------------------------------------------------------------------


class TreatyCondition(BaseModel):
    """A single mechanical condition within a treaty."""

    type: Literal["no_attack", "tribute", "military_support", "non_interference"]
    target_faction_id: str | None = None
    amount: int | None = None
    interval_ticks: int | None = None


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


async def create_treaty(
    session: AsyncSession,
    *,
    parties: list[str],
    terms_narrative: str,
    terms_conditions: list[TreatyCondition],
    signed_at_tick: int,
    expires_at_tick: int | None = None,
    binding_event_id: str | None = None,
) -> str:
    """Create a Treaty node and BOUND_BY edges for each party.

    Args:
        session: Active Neo4j async session.
        parties: List of faction IDs that sign the treaty.
        terms_narrative: Free-text description of treaty terms.
        terms_conditions: Structured list of mechanical conditions.
        signed_at_tick: Game tick when the treaty was signed.
        expires_at_tick: Optional expiry tick.
        binding_event_id: Optional event node that triggered the treaty.

    Returns:
        ID of the newly created Treaty node.
    """
    treaty_id = str(uuid.uuid4())
    conditions_json = json.dumps([c.model_dump() for c in terms_conditions])
    await session.run(
        CYPHER_CREATE_TREATY,
        id=treaty_id,
        terms_narrative=terms_narrative,
        terms_conditions=conditions_json,
        signed_at_tick=signed_at_tick,
        expires_at_tick=expires_at_tick,
        binding_event_id=binding_event_id,
    )
    for faction_id in parties:
        await session.run(
            CYPHER_CREATE_BOUND_BY,
            faction_id=faction_id,
            treaty_id=treaty_id,
            role="signatory",
        )
    return treaty_id


async def get_active_treaties_svc(
    session: AsyncSession,
    faction_id: str,
) -> list[dict[str, Any]]:
    """Return active treaties for a faction.

    Args:
        session: Active Neo4j async session.
        faction_id: ID of the Faction node.

    Returns:
        List of treaty dicts.
    """
    return await get_active_treaties(session, faction_id=faction_id)


async def expire_treaty(
    session: AsyncSession,
    treaty_id: str,
    tick: int,
) -> None:
    """Set a treaty's status to 'expired'.

    Args:
        session: Active Neo4j async session.
        treaty_id: ID of the Treaty node.
        tick: Current game tick (unused in write but kept for auditability).
    """
    await session.run(CYPHER_SET_TREATY_STATUS, treaty_id=treaty_id, status="expired")


async def break_treaty(
    session: AsyncSession,
    *,
    treaty_id: str,
    breaking_faction_id: str,
    tick: int,
) -> None:
    """Set a treaty's status to 'broken'.

    Args:
        session: Active Neo4j async session.
        treaty_id: ID of the Treaty node.
        breaking_faction_id: ID of the faction that broke the treaty.
        tick: Current game tick.
    """
    await session.run(CYPHER_SET_TREATY_STATUS, treaty_id=treaty_id, status="broken")


async def check_treaty_conditions_mechanical(
    session: AsyncSession,
    treaty_id: str,
    tick: int,
) -> list[str]:
    """Check structured conditions mechanically and return violated condition descriptions.

    Currently verifies presence of conditions. Specific condition types (tribute payment
    intervals etc.) require world-state queries not yet implemented — they are noted
    but return no violations at this layer.

    Args:
        session: Active Neo4j async session.
        treaty_id: ID of the Treaty node.
        tick: Current game tick.

    Returns:
        List of human-readable violation strings; empty means no violations detected.
    """
    conditions_json = await get_treaty_conditions(session, treaty_id=treaty_id)
    if conditions_json is None:
        return [f"treaty '{treaty_id}' not found"]
    try:
        raw = json.loads(conditions_json)
        conditions = [TreatyCondition(**c) for c in raw]
    except (json.JSONDecodeError, Exception):
        return [f"treaty '{treaty_id}' has malformed conditions"]

    violations: list[str] = []
    for condition in conditions:
        if condition.type == "tribute" and condition.interval_ticks is not None:
            if tick % condition.interval_ticks == 0 and tick > 0:
                violations.append(
                    f"tribute due: {condition.amount} every {condition.interval_ticks} ticks"
                )
    return violations


async def get_expiring_treaties_svc(
    session: AsyncSession,
    *,
    tick_id: int,
) -> list[str]:
    """Return IDs of treaties that have passed their expiry tick.

    Args:
        session: Active Neo4j async session.
        tick_id: Current game tick.

    Returns:
        List of treaty ID strings.
    """
    return await get_expiring_treaties(session, tick_id=tick_id)
