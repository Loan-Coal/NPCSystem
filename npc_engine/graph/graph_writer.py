"""
graph_writer.py - Transaction coordinator for graph mutation workflows.

Does NOT: define mutation policy bounds.

Dependencies injected: AsyncSession.
"""

import json
from datetime import datetime, timezone

from neo4j import AsyncSession

from config import Settings
from graph.delta_log_writer import write_delta_log
from graph.edge_schemas import RelationDeltaEntry
from graph.relation_writer import get_relation_values, set_relation_values
from mutation.delta_log_manager import append_delta
from mutation.modifier_bounds_validator import (
    DeltaValidationConfig,
    clamp_relation_values,
    validate_deltas,
)
from utils.errors import RelationEdgeNotFoundError


async def apply_relation_delta(
    session: AsyncSession,
    settings: Settings,
    src_id: str,
    dst_id: str,
    deltas: dict[str, int],
    cause_id: str,
    tick_id: int,
) -> dict[str, int]:
    """Validate and atomically apply relation deltas for one directed edge."""

    config = DeltaValidationConfig(
        max_delta_per_turn=settings.MAX_RELATION_DELTA_PER_TURN,
        max_delta_per_window=settings.MAX_RELATION_DELTA_PER_WINDOW,
        relation_window_size=settings.RELATION_WINDOW_SIZE,
    )

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
        return clamped
