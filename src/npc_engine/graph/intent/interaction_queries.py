"""
Module: interaction_queries
Layer: graph
Purpose: Read-only Neo4j queries for the interaction dispatch layer —
         sellable NPC inventory and player debt records.
Does NOT: mutate graph state, call LLM, or perform HTTP.
Dependencies injected: AsyncSession (caller-managed).
Used by: retrieval.context_builder, api.routes.interaction
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession


_CYPHER_SELLABLE_ITEMS = """
MATCH (c:Character {id: $npc_id})-[:OWNS]->(i:Item)
WHERE i.type IS NOT NULL
RETURN i.id        AS id,
       i.name      AS name,
       i.type      AS item_type,
       toInteger(i.value) AS base_value
ORDER BY toInteger(i.value) DESC
LIMIT $limit
"""

_CYPHER_CREATE_DEBT_EDGE = """
MATCH (debtor:Character {id: $debtor_id})
MATCH (creditor:Character {id: $creditor_id})
MERGE (debtor)-[d:HAS_DEBT {item_id: $item_id}]->(creditor)
SET d.amount      = $amount,
    d.due_tick    = $due_tick,
    d.created_at  = datetime(),
    d.settled     = false
RETURN d.amount AS amount
"""


async def get_sellable_items_for_npc(
    session: AsyncSession,
    *,
    npc_id: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return items the NPC owns that have a non-null type (tradeable proxy).

    Items without a type field are internal/non-tradeable and are excluded.
    Ordered by descending value so the most valuable items appear first in context.

    Args:
        session: Active Neo4j async session.
        npc_id: Character node ID of the NPC.
        limit: Maximum items to return (default 5).

    Returns:
        List of dicts with keys: id, name, item_type, base_value.
    """
    result = await session.run(_CYPHER_SELLABLE_ITEMS, npc_id=npc_id, limit=limit)
    return [dict(r) async for r in result]


async def write_debt_edge(
    session: AsyncSession,
    *,
    debtor_id: str,
    creditor_id: str,
    item_id: str,
    amount: int,
    current_tick: int,
    debt_duration_ticks: int = 100,
) -> None:
    """Create or update a HAS_DEBT edge from debtor to creditor for a deferred trade.

    Args:
        session: Active Neo4j async session.
        debtor_id: Character ID of the player owing the debt.
        creditor_id: Character ID of the NPC owed.
        item_id: Item node ID the debt is attached to.
        amount: Currency amount owed.
        current_tick: Current game tick (for due_tick computation).
        debt_duration_ticks: Number of ticks until the debt is due (default 100).
    """
    await session.run(
        _CYPHER_CREATE_DEBT_EDGE,
        debtor_id=debtor_id,
        creditor_id=creditor_id,
        item_id=item_id,
        amount=amount,
        due_tick=current_tick + debt_duration_ticks,
    )
