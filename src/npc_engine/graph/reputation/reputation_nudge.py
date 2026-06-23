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

from neo4j import AsyncSession, AsyncTransaction

from npc_engine.graph.relations.relation_writer import get_relation_values, set_relation_values
from npc_engine.graph.infra.transaction_coordinator import run_in_tx
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
    """Apply bounded trust/affection deltas to an existing RELATES_TO edge.

    Returns silently if the edge does not exist; never creates new edges.
    """
    result = await _read_modify_write(
        session, src_id=src_id, dst_id=dst_id,
        delta_trust=delta_trust, delta_affection=delta_affection,
    )
    if result is None:
        return
    new_trust, new_affection = result
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


async def _read_modify_write(
    session: AsyncSession,
    *,
    src_id: str,
    dst_id: str,
    delta_trust: int,
    delta_affection: int,
) -> tuple[int, int] | None:
    """Read-modify-write RELATES_TO scalars in one transaction; returns None if edge missing."""
    async def _work(tx: AsyncTransaction) -> tuple[int, int] | None:
        try:
            current = await get_relation_values(tx=tx, src_id=src_id, dst_id=dst_id)
        except RelationEdgeNotFoundError:
            return None
        new_trust = _clamp(current["trust"] + delta_trust)
        new_affection = _clamp(current["affection"] + delta_affection)
        await set_relation_values(
            tx=tx,
            src_id=src_id,
            dst_id=dst_id,
            new_values={"trust": new_trust, "fear": current["fear"], "affection": new_affection},
        )
        return new_trust, new_affection

    return await run_in_tx(session, _work)


def _clamp(value: int) -> int:
    """Clamp value to [SCALAR_MIN, SCALAR_MAX]."""
    return max(SCALAR_MIN, min(SCALAR_MAX, value))
