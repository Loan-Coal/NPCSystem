"""
relation_delta_writer.py - Validates and atomically applies relation deltas within one transaction.
Layer: graph
Purpose: Validates and atomically applies relation deltas within one transaction.

Does NOT: handle currency or item transfers.

Dependencies injected: AsyncSession, Settings.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from time import perf_counter

from neo4j import AsyncSession, AsyncTransaction

from npc_engine.config import Settings
from npc_engine.graph.delta_log_writer import write_delta_log
from npc_engine.graph.relation_writer import get_relation_values, set_relation_values
from npc_engine.graph.transaction_coordinator import run_in_tx
from npc_engine.graph.write_metrics import record_graph_write_metrics
from npc_engine.mutation.delta_log_manager import RelationDeltaEntry, append_delta
from npc_engine.mutation.modifier_bounds_validator import DeltaValidationConfig, clamp_relation_values, validate_deltas
from npc_engine.utils.errors import RelationEdgeNotFoundError

_CYPHER_GET_DELTA_LOG = (
    "MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id}) "
    "RETURN coalesce(r.delta_log, '[]') AS delta_log"
)


async def _load_canonical_delta_log(
    tx: AsyncTransaction, src_id: str, dst_id: str
) -> list[RelationDeltaEntry]:
    """Read the edge's delta_log and canonicalize it into validated entries.

    Args:
        tx: Active Neo4j transaction.
        src_id: ID of the source character node.
        dst_id: ID of the destination character node.

    Returns:
        The canonicalized delta-log entries (timestamps backfilled where absent).

    Raises:
        RelationEdgeNotFoundError: If the RELATES_TO edge between src and dst is missing.
    """
    result = await tx.run(_CYPHER_GET_DELTA_LOG, src_id=src_id, dst_id=dst_id)
    record = await result.single()
    if record is None:
        raise RelationEdgeNotFoundError(src_id=src_id, dst_id=dst_id)
    canonical_log: list[RelationDeltaEntry] = []
    for entry in json.loads(record["delta_log"]):
        if "timestamp" not in entry or entry["timestamp"] is None:
            entry = {**entry, "timestamp": datetime.now(timezone.utc).isoformat()}
        canonical_log.append(RelationDeltaEntry.model_validate(entry))
    return canonical_log


async def _apply_relation_delta_tx(
    tx: AsyncTransaction,
    *,
    config: DeltaValidationConfig,
    window_size: int,
    src_id: str,
    dst_id: str,
    deltas: dict[str, int],
    cause_id: str,
    tick_id: int,
) -> dict[str, int]:
    """Validate, clamp, and persist one relation delta within the caller's transaction.

    Returns:
        The clamped final relation values after applying the validated deltas.
    """
    current = await get_relation_values(tx=tx, src_id=src_id, dst_id=dst_id)
    canonical_log = await _load_canonical_delta_log(tx, src_id, dst_id)
    validated = validate_deltas(proposed_deltas=deltas, delta_log=canonical_log, config=config)
    clamped = clamp_relation_values(current_values=current, deltas=validated)
    await set_relation_values(tx=tx, src_id=src_id, dst_id=dst_id, new_values=clamped)
    new_delta_log = append_delta(
        delta_log=canonical_log,
        tick_id=tick_id,
        cause_id=cause_id,
        deltas=validated,
        max_entries=window_size,
    )
    payload = [entry.model_dump(mode="json") for entry in new_delta_log]
    await write_delta_log(tx=tx, src_id=src_id, dst_id=dst_id, delta_log_payload=payload)
    return clamped


async def apply_relation_delta(
    session: AsyncSession,
    settings: Settings,
    src_id: str,
    dst_id: str,
    deltas: dict[str, int],
    cause_id: str,
    tick_id: int,
) -> dict[str, int]:
    """Validate and atomically apply relation deltas for one directed edge.

    Args:
        session: Active Neo4j async session the coordinator opens a transaction on.
        settings: Application settings providing delta bound configuration.
        src_id: ID of the source character node.
        dst_id: ID of the destination character node.
        deltas: Proposed per-field relation deltas (e.g. {"trust": 5, "fear": -2}).
        cause_id: Identifier of the event or action that triggered the delta.
        tick_id: Game tick at which the delta was applied.

    Returns:
        Dict of clamped final relation values after applying validated deltas.

    Raises:
        RelationEdgeNotFoundError: If the RELATES_TO edge between src and dst is missing.
        RelationDeltaExceededError: If any proposed delta exceeds configured bounds.
    """
    started_at = perf_counter()
    config = DeltaValidationConfig(
        max_delta_per_turn=settings.MAX_RELATION_DELTA_PER_TURN,
        max_delta_per_window=settings.MAX_RELATION_DELTA_PER_WINDOW,
        relation_window_size=settings.RELATION_WINDOW_SIZE,
    )

    async def _work(tx: AsyncTransaction) -> dict[str, int]:
        return await _apply_relation_delta_tx(
            tx,
            config=config,
            window_size=settings.RELATION_WINDOW_SIZE,
            src_id=src_id,
            dst_id=dst_id,
            deltas=deltas,
            cause_id=cause_id,
            tick_id=tick_id,
        )

    try:
        clamped = await run_in_tx(session, _work)
        record_graph_write_metrics(operation="relation_delta", result="success", started_at=started_at)
        return clamped
    except Exception:
        record_graph_write_metrics(operation="relation_delta", result="failure", started_at=started_at)
        raise
