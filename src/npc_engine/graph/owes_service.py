"""
Module: owes_service
Layer: graph
Purpose: Functions for creating and retrieving OWES edges between Characters.
Does NOT: implement business logic, validate request payloads, or call LLMs.
Dependencies: graph.owes_queries
Dependencies injected: AsyncSession.
Used by: npc_engine.api.routes.debts, npc_engine.retrieval.context.context_builder
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession, AsyncTransaction

from npc_engine.graph.owes_queries import (
    CYPHER_CREATE_DEBT,
    CYPHER_UPDATE_DEBT_STATUS,
    get_debts_for_character,
)
from npc_engine.graph.transaction_coordinator import run_in_tx

_VALID_KINDS = frozenset({"money", "favor", "item", "service"})
_VALID_STATUSES = frozenset({"pending", "fulfilled", "defaulted"})


async def create_debt(
    session: AsyncSession,
    *,
    debtor_id: str,
    creditor_id: str,
    kind: str,
    magnitude: str,
    due_by: str = "",
) -> None:
    """Create or update an OWES edge from debtor to creditor.

    The edge is MERGE-d on (debtor, creditor, kind), so calling this twice
    with the same triple updates magnitude, due_by, and resets status to pending.

    Args:
        session: Active Neo4j async session.
        debtor_id: ID of the character who owes.
        creditor_id: ID of the character who is owed.
        kind: Obligation type — one of money, favor, item, service.
        magnitude: Numeric or descriptive amount (e.g. "50" or "a meal").
        due_by: Game-time JSON string for the deadline; empty string if open-ended.

    Raises:
        ValueError: If kind is not one of the allowed values.
    """
    if kind not in _VALID_KINDS:
        raise ValueError(f"kind must be one of {sorted(_VALID_KINDS)}, got {kind!r}")
    async def _work(tx: AsyncTransaction) -> None:
        await tx.run(
            CYPHER_CREATE_DEBT,
            debtor_id=debtor_id,
            creditor_id=creditor_id,
            kind=kind,
            magnitude=magnitude,
            due_by=due_by,
            status="pending",
        )

    await run_in_tx(session, _work)


async def get_debts_for_character_svc(
    session: AsyncSession,
    *,
    character_id: str,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Fetch pending obligations for a character (as debtor or creditor).

    Args:
        session: Active Neo4j async session.
        character_id: ID of the character node.
        k: Maximum number of obligations to return.

    Returns:
        List of debt dicts ordered by due_by ascending.
    """
    return await get_debts_for_character(session, character_id=character_id, k=k)


async def update_debt_status(
    session: AsyncSession,
    *,
    debtor_id: str,
    creditor_id: str,
    status: str,
) -> None:
    """Update the status of an OWES edge.

    Args:
        session: Active Neo4j async session.
        debtor_id: ID of the debtor character.
        creditor_id: ID of the creditor character.
        status: New status — one of pending, fulfilled, defaulted.

    Raises:
        ValueError: If status is not one of the allowed values.
    """
    if status not in _VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(_VALID_STATUSES)}, got {status!r}")
    async def _work(tx: AsyncTransaction) -> None:
        await tx.run(
            CYPHER_UPDATE_DEBT_STATUS,
            debtor_id=debtor_id,
            creditor_id=creditor_id,
            status=status,
        )

    await run_in_tx(session, _work)
