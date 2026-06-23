"""
Module: owes_queries
Layer: graph
Purpose: Cypher query strings and read accessors for OWES edges between Characters.
Does NOT: execute business logic or validate payloads.
Dependencies: None (Cypher strings only).
Dependencies injected: AsyncSession.
Used by: npc_engine.graph.economy.owes_service
"""

from __future__ import annotations

from typing import Any, cast

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Write queries
# ---------------------------------------------------------------------------

CYPHER_CREATE_DEBT = """
MATCH (debtor:Character {id: $debtor_id})
MATCH (creditor:Character {id: $creditor_id})
MERGE (debtor)-[r:OWES {kind: $kind}]->(creditor)
SET r.magnitude = $magnitude,
    r.due_by    = $due_by,
    r.status    = $status
"""

CYPHER_UPDATE_DEBT_STATUS = """
MATCH (debtor:Character {id: $debtor_id})-[r:OWES]->(creditor:Character {id: $creditor_id})
SET r.status = $status
"""

# ---------------------------------------------------------------------------
# Read queries
# ---------------------------------------------------------------------------

CYPHER_GET_DEBTS_AS_DEBTOR = """
MATCH (debtor:Character {id: $character_id})-[r:OWES]->(creditor:Character)
WHERE r.status = 'pending'
RETURN creditor.id   AS other_id,
       'debtor'       AS role,
       r.kind         AS kind,
       r.magnitude    AS magnitude,
       r.due_by       AS due_by,
       r.status       AS status
ORDER BY r.due_by ASC
LIMIT $k
"""

CYPHER_GET_DEBTS_AS_CREDITOR = """
MATCH (debtor:Character)-[r:OWES]->(creditor:Character {id: $character_id})
WHERE r.status = 'pending'
RETURN debtor.id     AS other_id,
       'creditor'    AS role,
       r.kind        AS kind,
       r.magnitude   AS magnitude,
       r.due_by      AS due_by,
       r.status      AS status
ORDER BY r.due_by ASC
LIMIT $k
"""


async def get_debts_for_character(
    session: AsyncSession,
    *,
    character_id: str,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Fetch pending obligations where the character is debtor or creditor.

    Returns up to k records ordered by due_by ascending (most urgent first).
    Debtor rows have role='debtor'; creditor rows have role='creditor'.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        k: Maximum number of obligations to return per role direction.

    Returns:
        Combined list of debt property dicts ordered by due_by ascending.
    """
    as_debtor_result = await session.run(
        CYPHER_GET_DEBTS_AS_DEBTOR,
        character_id=character_id,
        k=k,
    )
    as_debtor = cast(
        list[dict[str, Any]],
        [dict(record) async for record in as_debtor_result],
    )

    as_creditor_result = await session.run(
        CYPHER_GET_DEBTS_AS_CREDITOR,
        character_id=character_id,
        k=k,
    )
    as_creditor = cast(
        list[dict[str, Any]],
        [dict(record) async for record in as_creditor_result],
    )

    combined = as_debtor + as_creditor
    combined.sort(key=lambda row: row.get("due_by") or "")
    return combined[:k]
