"""
Module: reputation_nudge
Layer: graph
Purpose: Thin write helper for the 1-hop reputation propagation engine (EXP-52).
         Opens a single transaction, reads the existing RELATES_TO edge between
         src_id and dst_id, applies bounded deltas, and writes back.
         Returns immediately (without writing) if no edge exists — never creates edges.
Does NOT: contain engine logic, derive Standing, call LLMs, or open long-lived sessions.
Dependencies injected: neo4j.AsyncSession (caller-managed).
Used by: npc_engine.engines.reputation.reputation_engine (via injection).
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession

from npc_engine.graph.relation_writer import get_relation_values, set_relation_values
from npc_engine.utils.errors import RelationEdgeNotFoundError
from npc_engine.utils.logging import get_logger

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCALAR_MIN: int = -100
SCALAR_MAX: int = 100

logger: logging.Logger = get_logger()


async def apply_trust_nudge(
    session: AsyncSession,
    *,
    src_id: str,
    dst_id: str,
    delta_trust: int,
    delta_affection: int,
) -> None:
    """Apply bounded trust and affection deltas to an existing RELATES_TO edge.

    Opens a single transaction, reads the current scalars, applies the deltas
    (clamped to [SCALAR_MIN, SCALAR_MAX]), and writes back. If no edge exists
    between src_id and dst_id the function returns silently without creating one.

    Args:
        session: Active Neo4j async session used to open the transaction.
        src_id: ID of the source character node (the bridge NPC in propagation).
        dst_id: ID of the destination character node (typically the player).
        delta_trust: Signed trust delta to apply. Clamped after application.
        delta_affection: Signed affection delta to apply. Clamped after application.

    Raises:
        No domain errors propagated — missing edges are silently skipped.
        Unexpected Neo4j transport errors are re-raised as-is.
    """
    tx = await session.begin_transaction()
    async with tx:
        try:
            current = await get_relation_values(tx=tx, src_id=src_id, dst_id=dst_id)
        except RelationEdgeNotFoundError:
            return

        new_trust = _clamp(current["trust"] + delta_trust)
        new_affection = _clamp(current["affection"] + delta_affection)

        await set_relation_values(
            tx=tx,
            src_id=src_id,
            dst_id=dst_id,
            new_values={
                "trust": new_trust,
                "fear": current["fear"],
                "affection": new_affection,
            },
        )

    logger.info(
        "reputation_nudge_written",
        extra={
            "npc_id": src_id,
            "player_id": dst_id,
            "delta_trust": delta_trust,
            "delta_affection": delta_affection,
            "new_trust": new_trust,
        },
    )


def _clamp(value: int) -> int:
    """Clamp value to [SCALAR_MIN, SCALAR_MAX]."""
    return max(SCALAR_MIN, min(SCALAR_MAX, value))
