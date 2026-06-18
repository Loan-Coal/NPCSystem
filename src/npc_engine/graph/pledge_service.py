"""
Module: pledge_service
Layer: graph
Purpose: Create, read, and break PLEDGE edges between characters. On break, applies
         trust drop via RELATES_TO and faction standing swing via STANDS_WITH.
Does NOT: call LLMs, detect violations, or orchestrate oath engine scheduling.
Dependencies injected: AsyncSession.
Dependencies: graph.pledge_queries
Used by: npc_engine.engines.oath.oath_engine, npc_engine.api.routes.pledges,
         npc_engine.graph.pledge_violation_service
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.graph.pledge_queries import (
    CYPHER_ADJUST_STANDS_WITH,
    CYPHER_CREATE_PLEDGE,
    CYPHER_DEACTIVATE_PLEDGE,
    CYPHER_GET_FACTION_FOR_CHARACTER,
    CYPHER_TRUST_DROP,
    get_all_active_pledgers,
    get_expiring_pledges,
    get_pledges_for_character,
)

_TRUST_DROP_ON_BREAK = 30
_FACTION_SWING_ON_BREAK = -15


async def create_pledge(
    session: AsyncSession,
    *,
    pledger_id: str,
    pledgee_id: str,
    pledge_type: str,
    tick: int,
    expires_at_tick: int | None = None,
    witness_id: str | None = None,
    binding_event_id: str | None = None,
    severity: int = 50,
) -> None:
    """Create a new PLEDGE edge from pledger to pledgee.

    Args:
        session: Active Neo4j async session.
        pledger_id: ID of the character making the pledge.
        pledgee_id: ID of the character receiving the pledge.
        pledge_type: One of protect, serve, kill, marry, mentor, fealty, vendetta.
        tick: Current game tick (stored as sworn_at_tick).
        expires_at_tick: Optional tick at which the pledge expires automatically.
        witness_id: Optional character who witnessed the pledge.
        binding_event_id: Optional event node ID that caused this pledge.
        severity: How serious this pledge is (0–100).
    """
    await session.run(
        CYPHER_CREATE_PLEDGE,
        pledger_id=pledger_id,
        pledgee_id=pledgee_id,
        pledge_type=pledge_type,
        sworn_at_tick=tick,
        expires_at_tick=expires_at_tick,
        witness_character_id=witness_id,
        binding_event_id=binding_event_id,
        severity=severity,
    )


async def get_pledges_for_character_svc(
    session: AsyncSession,
    character_id: str,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    """Return pledges where character is the pledger.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node.
        active_only: When True, return only active pledges.

    Returns:
        List of pledge dicts.
    """
    return await get_pledges_for_character(session, character_id=character_id, active_only=active_only)


async def break_pledge(
    session: AsyncSession,
    *,
    pledger_id: str,
    pledgee_id: str,
    pledge_type: str,
    tick: int,
) -> None:
    """Deactivate a pledge and apply relationship consequences.

    Applies:
    1. RELATES_TO trust drop (pledger → pledgee and pledgee → pledger)
    2. STANDS_WITH swing for pledger's and pledgee's factions (if they belong to one)

    Args:
        session: Active Neo4j async session.
        pledger_id: ID of the character who breaks the pledge.
        pledgee_id: ID of the character owed the pledge.
        pledge_type: Pledge type string; used to identify the correct edge.
        tick: Current game tick (unused in writes but kept for auditability).
    """
    await session.run(
        CYPHER_DEACTIVATE_PLEDGE,
        pledger_id=pledger_id,
        pledgee_id=pledgee_id,
        pledge_type=pledge_type,
    )

    # Trust drop — both directions
    for src, dst in [(pledger_id, pledgee_id), (pledgee_id, pledger_id)]:
        await session.run(CYPHER_TRUST_DROP, src_id=src, dst_id=dst, drop=_TRUST_DROP_ON_BREAK)

    # Faction standing swing — if each character belongs to a faction
    pledger_faction = await _get_faction(session, pledger_id)
    pledgee_faction = await _get_faction(session, pledgee_id)
    if pledger_faction and pledgee_faction and pledger_faction != pledgee_faction:
        for src_f, dst_f in [(pledger_faction, pledgee_faction), (pledgee_faction, pledger_faction)]:
            await session.run(
                CYPHER_ADJUST_STANDS_WITH,
                src_faction_id=src_f,
                dst_faction_id=dst_f,
                delta=_FACTION_SWING_ON_BREAK,
            )


async def get_all_active_pledgers_svc(
    session: AsyncSession,
) -> list[str]:
    """Return distinct IDs of all characters with at least one active pledge.

    Args:
        session: Active Neo4j async session.

    Returns:
        List of pledger character IDs.
    """
    return await get_all_active_pledgers(session)


async def get_expiring_pledges_svc(
    session: AsyncSession,
    *,
    tick_id: int,
) -> list[dict[str, Any]]:
    """Return active pledges that have reached or passed their expiry tick.

    Args:
        session: Active Neo4j async session.
        tick_id: Current game tick.

    Returns:
        List of pledge dicts for expired pledges.
    """
    return await get_expiring_pledges(session, tick_id=tick_id)


async def _get_faction(session: AsyncSession, character_id: str) -> str | None:
    result = await session.run(CYPHER_GET_FACTION_FOR_CHARACTER, character_id=character_id)
    record = await result.single()
    if record is None:
        return None
    return str(record["faction_id"])
