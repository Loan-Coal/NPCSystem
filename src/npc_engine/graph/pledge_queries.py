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
    return [dict(record) async for record in result]
