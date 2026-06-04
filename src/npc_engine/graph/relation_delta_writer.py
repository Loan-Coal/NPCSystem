"""
relation_delta_writer.py - Validates and atomically applies relation deltas within one transaction.
Layer: graph
Purpose: (auto-detected — review)

Does NOT: handle currency or item transfers.

Dependencies injected: AsyncSession, Settings.
"""

import json
from datetime import datetime, timezone
from time import perf_counter

from neo4j import AsyncSession

from npc_engine.config import Settings
from npc_engine.graph.delta_log_writer import write_delta_log
from npc_engine.graph.relation_writer import get_relation_values, set_relation_values
from npc_engine.graph.write_metrics import record_graph_write_metrics
from npc_engine.mutation.delta_log_manager import RelationDeltaEntry, append_delta
from npc_engine.mutation.modifier_bounds_validator import DeltaValidationConfig, clamp_relation_values, validate_deltas
from npc_engine.utils.errors import RelationEdgeNotFoundError


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
        session: Active Neo4j async session used to begin the transaction.
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

    try:
        tx = await session.begin_transaction()
        async with tx:
            current = await get_relation_values(tx=tx, src_id=src_id, dst_id=dst_id)
            relation_result = await tx.run(
                "MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id}) "
                "RETURN coalesce(r.delta_log, '[]') AS delta_log",
                src_id=src_id,
                dst_id=dst_id,
            )
            relation_record = await relation_result.single()
            if relation_record is None:
                raise RelationEdgeNotFoundError(src_id=src_id, dst_id=dst_id)
            raw_log = relation_record["delta_log"] if relation_record else "[]"
            parsed_log = json.loads(raw_log)

            canonical_log = []
            for entry in parsed_log:
                if "timestamp" not in entry or entry["timestamp"] is None:
                    entry = {
                        **entry,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                canonical_log.append(RelationDeltaEntry.model_validate(entry))
            validated = validate_deltas(
                proposed_deltas=deltas,
                delta_log=canonical_log,
                config=config,
            )
            clamped = clamp_relation_values(current_values=current, deltas=validated)
            await set_relation_values(tx=tx, src_id=src_id, dst_id=dst_id, new_values=clamped)

            new_delta_log = append_delta(
                delta_log=canonical_log,
                tick_id=tick_id,
                cause_id=cause_id,
                deltas=validated,
                max_entries=settings.RELATION_WINDOW_SIZE,
            )
            payload = [entry.model_dump(mode="json") for entry in new_delta_log]
            await write_delta_log(tx=tx, src_id=src_id, dst_id=dst_id, delta_log_payload=payload)
            await tx.commit()
            record_graph_write_metrics(operation="relation_delta", result="success", started_at=started_at)
            return clamped
    except Exception:
        record_graph_write_metrics(operation="relation_delta", result="failure", started_at=started_at)
        raise
