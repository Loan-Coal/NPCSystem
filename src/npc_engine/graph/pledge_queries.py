"""
Module: pledge_queries
Layer: graph
Purpose: Cypher queries for PLEDGE edges between characters.
Does NOT: implement business logic or call LLMs.
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.pledge_service
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

CYPHER_CREATE_PLEDGE = """
MATCH (pledger:Character {id: $pledger_id}), (pledgee:Character {id: $pledgee_id})
CREATE (pledger)-[e:PLEDGE {
    pledge_type:          $pledge_type,
    sworn_at_tick:        $sworn_at_tick,
    expires_at_tick:      $expires_at_tick,
    witness_character_id: $witness_character_id,
    binding_event_id:     $binding_event_id,
    is_active:            true,
    severity:             $severity
}]->(pledgee)
"""

CYPHER_GET_PLEDGES_FOR_CHARACTER = """
MATCH (pledger:Character {id: $character_id})-[e:PLEDGE]->(pledgee:Character)
WHERE e.is_active = $active_only OR $active_only = false
RETURN pledger.id AS pledger_id,
       pledgee.id AS pledgee_id,
       pledgee.name AS pledgee_name,
       e.pledge_type AS pledge_type,
       e.sworn_at_tick AS sworn_at_tick,
       e.expires_at_tick AS expires_at_tick,
       e.is_active AS is_active,
       e.severity AS severity,
       e.binding_event_id AS binding_event_id
ORDER BY e.sworn_at_tick DESC
"""

CYPHER_DEACTIVATE_PLEDGE = """
MATCH (pledger:Character {id: $pledger_id})-[e:PLEDGE]->(pledgee:Character {id: $pledgee_id})
WHERE e.pledge_type = $pledge_type AND e.is_active = true
SET e.is_active = false
RETURN count(e) AS updated
"""

CYPHER_TRUST_DROP = """
MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id})
SET r.trust = CASE WHEN r.trust - $drop < -100 THEN -100 ELSE r.trust - $drop END,
    r.last_updated_at = datetime()
"""

CYPHER_GET_FACTION_FOR_CHARACTER = """
MATCH (c:Character {id: $character_id})-[:MEMBER_OF]->(f:Faction)
RETURN f.id AS faction_id
LIMIT 1
"""

CYPHER_ADJUST_STANDS_WITH = """
MATCH (a:Faction {id: $src_faction_id})
MATCH (b:Faction {id: $dst_faction_id})
MERGE (a)-[r:STANDS_WITH]->(b)
ON CREATE SET r.standing = $delta
ON MATCH SET r.standing = CASE
    WHEN r.standing + $delta > 100 THEN 100
    WHEN r.standing + $delta < -100 THEN -100
    ELSE r.standing + $delta
END,
r.last_changed_at = datetime()
"""

CYPHER_GET_EXPIRING_PLEDGES = """
MATCH (pledger:Character)-[e:PLEDGE]->(pledgee:Character)
WHERE e.is_active = true
  AND e.expires_at_tick IS NOT NULL
  AND e.expires_at_tick <= $tick_id
RETURN pledger.id AS pledger_id,
       pledgee.id AS pledgee_id,
       e.pledge_type AS pledge_type,
       e.binding_event_id AS binding_event_id
"""


async def get_pledges_for_character(
    session: AsyncSession,
    *,
    character_id: str,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    """Fetch pledges where character is the pledger.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node.
        active_only: When True, return only active pledges.

    Returns:
        List of pledge dicts ordered by sworn_at_tick descending.
    """
    result = await session.run(
        CYPHER_GET_PLEDGES_FOR_CHARACTER,
        character_id=character_id,
        active_only=active_only,
    )
    return [dict(record) async for record in result]


async def get_expiring_pledges(
    session: AsyncSession,
    *,
    tick_id: int,
) -> list[dict[str, Any]]:
    """Fetch active pledges that have reached or passed their expiry tick.

    Args:
        session: Active Neo4j async session.
        tick_id: Current game tick.

    Returns:
        List of pledge dicts for pledges that should now expire.
    """
    result = await session.run(CYPHER_GET_EXPIRING_PLEDGES, tick_id=tick_id)
    try:
        return [dict(record) async for record in result]
    finally:
        await result.consume()


# ---------------------------------------------------------------------------
# Violation detection queries
# ---------------------------------------------------------------------------

CYPHER_GET_ACTIVE_PLEDGES_FOR_PLEDGER = """
MATCH (pledger:Character {id: $pledger_id})-[p:PLEDGE]->(pledgee:Character)
WHERE p.is_active = true
RETURN pledgee.id AS pledgee_id,
       p.pledge_type AS pledge_type,
       toInteger(p.sworn_at_tick) AS sworn_at_tick,
       toInteger(p.severity) AS severity
"""

CYPHER_GET_WITNESSED_VIOLATIONS = """
MATCH (:Character)-[w:WITNESSED]->(subject:Character {id: $pledger_id})
WHERE toInteger(w.witnessed_at_tick) >= $since_tick
  AND w.action_type IN $action_types
RETURN w.action_type AS action_type,
       w.event_id AS event_id,
       toInteger(w.witnessed_at_tick) AS witnessed_at_tick
LIMIT 1
"""

CYPHER_GET_PARTICIPATED_VIOLATIONS = """
MATCH (pledger:Character {id: $pledger_id})-[p:PARTICIPATED_IN]->(evt:Event)
WHERE toInteger(evt.tick_id) >= $since_tick
  AND p.role IN $roles
RETURN p.role AS role,
       evt.id AS event_id,
       toInteger(evt.tick_id) AS tick_id
LIMIT 1
"""

CYPHER_GET_ALL_ACTIVE_PLEDGERS = """
MATCH (pledger:Character)-[p:PLEDGE]->()
WHERE p.is_active = true
RETURN DISTINCT pledger.id AS pledger_id
"""


async def get_active_pledges_for_pledger(
    session: AsyncSession,
    *,
    pledger_id: str,
) -> list[dict[str, Any]]:
    """Return all active pledges for a given pledger.

    Args:
        session: Active Neo4j async session.
        pledger_id: ID of the Character node making the pledges.

    Returns:
        List of dicts with pledgee_id, pledge_type, sworn_at_tick, severity.
    """
    result = await session.run(
        CYPHER_GET_ACTIVE_PLEDGES_FOR_PLEDGER, pledger_id=pledger_id
    )
    try:
        return [dict(record) async for record in result]
    finally:
        await result.consume()


async def get_witnessed_violations(
    session: AsyncSession,
    *,
    pledger_id: str,
    since_tick: int,
    action_types: list[str],
) -> list[dict[str, Any]]:
    """Return WITNESSED edges where pledger was the subject and action_type violated a pledge.

    Args:
        session: Active Neo4j async session.
        pledger_id: ID of the Character whose actions we are checking.
        since_tick: Only consider WITNESSED edges at or after this tick.
        action_types: Action types that constitute a violation for this pledge type.

    Returns:
        List of witness records (at most one per call, limited at DB level).
    """
    if not action_types:
        return []
    result = await session.run(
        CYPHER_GET_WITNESSED_VIOLATIONS,
        pledger_id=pledger_id,
        since_tick=since_tick,
        action_types=action_types,
    )
    try:
        return [dict(record) async for record in result]
    finally:
        await result.consume()


async def get_participated_violations(
    session: AsyncSession,
    *,
    pledger_id: str,
    since_tick: int,
    roles: list[str],
) -> list[dict[str, Any]]:
    """Return PARTICIPATED_IN edges where pledger's role violated a pledge.

    Args:
        session: Active Neo4j async session.
        pledger_id: ID of the Character to check.
        since_tick: Only consider Event nodes at or after this tick.
        roles: Roles that constitute a violation for this pledge type.

    Returns:
        List of participation violation records (at most one per call, limited at DB level).
    """
    if not roles:
        return []
    result = await session.run(
        CYPHER_GET_PARTICIPATED_VIOLATIONS,
        pledger_id=pledger_id,
        since_tick=since_tick,
        roles=roles,
    )
    try:
        return [dict(record) async for record in result]
    finally:
        await result.consume()


async def get_all_active_pledgers(
    session: AsyncSession,
) -> list[str]:
    """Return all distinct Character IDs that currently hold at least one active pledge.

    Args:
        session: Active Neo4j async session.

    Returns:
        List of pledger character IDs.
    """
    result = await session.run(CYPHER_GET_ALL_ACTIVE_PLEDGERS)
    try:
        return [record["pledger_id"] async for record in result]
    finally:
        await result.consume()
