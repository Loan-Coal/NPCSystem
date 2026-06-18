"""
Module: treaty_queries
Layer: graph
Purpose: Cypher queries for Treaty nodes and BOUND_BY edges.
Does NOT: implement business logic or call LLMs.
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.treaty_service
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

CYPHER_CREATE_TREATY = """
CREATE (t:Treaty {
    id:               $id,
    terms_narrative:  $terms_narrative,
    terms_conditions: $terms_conditions,
    signed_at_tick:   $signed_at_tick,
    expires_at_tick:  $expires_at_tick,
    binding_event_id: $binding_event_id,
    status:           'active'
})
RETURN t.id AS treaty_id
"""

CYPHER_CREATE_BOUND_BY = """
MATCH (f:Faction {id: $faction_id}), (t:Treaty {id: $treaty_id})
CREATE (f)-[:BOUND_BY {role: $role}]->(t)
"""

CYPHER_GET_ACTIVE_TREATIES = """
MATCH (f:Faction {id: $faction_id})-[:BOUND_BY]->(t:Treaty {status: 'active'})
RETURN t.id AS id,
       t.terms_narrative AS terms_narrative,
       t.terms_conditions AS terms_conditions,
       t.signed_at_tick AS signed_at_tick,
       t.expires_at_tick AS expires_at_tick,
       t.status AS status
"""

CYPHER_SET_TREATY_STATUS = """
MATCH (t:Treaty {id: $treaty_id})
SET t.status = $status
"""

CYPHER_GET_EXPIRING_TREATIES = """
MATCH (t:Treaty {status: 'active'})
WHERE t.expires_at_tick IS NOT NULL
  AND t.expires_at_tick <= $tick_id
RETURN t.id AS id
"""

CYPHER_GET_TREATY_CONDITIONS = """
MATCH (t:Treaty {id: $treaty_id})
RETURN t.terms_conditions AS terms_conditions,
       t.status AS status
"""

CYPHER_GET_TREATY_PARTIES = """
MATCH (f:Faction)-[:BOUND_BY]->(t:Treaty {id: $treaty_id})
RETURN f.id AS faction_id
"""

CYPHER_GET_ALL_ACTIVE_TREATY_IDS = """
MATCH (t:Treaty {status: 'active'})
RETURN t.id AS id
"""

CYPHER_GET_FACTION_TREASURY = """
MATCH (f:Faction {id: $faction_id})
RETURN coalesce(f.treasury, 0) AS treasury
"""

CYPHER_DEDUCT_FACTION_TREASURY = """
MATCH (f:Faction {id: $faction_id})
SET f.treasury = coalesce(f.treasury, 0) - $amount,
    f.last_graph_updated_at = datetime()
RETURN coalesce(f.treasury, 0) AS treasury
"""


async def get_active_treaties(
    session: AsyncSession,
    *,
    faction_id: str,
) -> list[dict[str, Any]]:
    """Fetch active treaties for a faction.

    Args:
        session: Active Neo4j async session.
        faction_id: ID of the Faction node.

    Returns:
        List of treaty dicts.
    """
    result = await session.run(CYPHER_GET_ACTIVE_TREATIES, faction_id=faction_id)
    return [dict(record) async for record in result]


async def get_expiring_treaties(
    session: AsyncSession,
    *,
    tick_id: int,
) -> list[str]:
    """Return IDs of active treaties that have reached or passed their expiry tick.

    Args:
        session: Active Neo4j async session.
        tick_id: Current game tick.

    Returns:
        List of treaty ID strings.
    """
    result = await session.run(CYPHER_GET_EXPIRING_TREATIES, tick_id=tick_id)
    return [record["id"] async for record in result]


async def get_treaty_conditions(
    session: AsyncSession,
    *,
    treaty_id: str,
) -> str | None:
    """Fetch the terms_conditions JSON string for a treaty.

    Args:
        session: Active Neo4j async session.
        treaty_id: ID of the Treaty node.

    Returns:
        JSON string of conditions or None if treaty not found.
    """
    result = await session.run(CYPHER_GET_TREATY_CONDITIONS, treaty_id=treaty_id)
    record = await result.single()
    if record is None:
        return None
    return str(record["terms_conditions"])


async def get_treaty_parties(
    session: AsyncSession,
    *,
    treaty_id: str,
) -> list[str]:
    """Fetch faction IDs bound by a treaty.

    Args:
        session: Active Neo4j async session.
        treaty_id: ID of the Treaty node.

    Returns:
        List of faction ID strings.
    """
    result = await session.run(CYPHER_GET_TREATY_PARTIES, treaty_id=treaty_id)
    return [record["faction_id"] async for record in result]


async def get_all_active_treaty_ids(session: AsyncSession) -> list[str]:
    """Return IDs of all active treaties.

    Args:
        session: Active Neo4j async session.

    Returns:
        List of treaty ID strings.
    """
    result = await session.run(CYPHER_GET_ALL_ACTIVE_TREATY_IDS)
    return [record["id"] async for record in result]


async def get_faction_treasury(session: AsyncSession, *, faction_id: str) -> int:
    """Return the treasury balance for a faction (0 if not set).

    Args:
        session: Active Neo4j async session.
        faction_id: ID of the Faction node.

    Returns:
        Integer treasury balance.
    """
    result = await session.run(CYPHER_GET_FACTION_TREASURY, faction_id=faction_id)
    record = await result.single()
    if record is None:
        return 0
    return int(record["treasury"])


async def deduct_faction_treasury(
    session: AsyncSession,
    *,
    faction_id: str,
    amount: int,
) -> int:
    """Deduct amount from a faction's treasury and return the new balance.

    Args:
        session: Active Neo4j async session.
        faction_id: ID of the Faction node.
        amount: Amount to deduct.

    Returns:
        New treasury balance after deduction.
    """
    result = await session.run(CYPHER_DEDUCT_FACTION_TREASURY, faction_id=faction_id, amount=amount)
    record = await result.single()
    if record is None:
        return 0
    return int(record["treasury"])
