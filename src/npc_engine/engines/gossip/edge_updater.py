"""
edge_updater.py - Appends gossip interaction metadata to relation delta logs.
Layer: engines
Purpose: (auto-detected — review)

Does NOT: enforce mutation bounds.

Dependencies injected: AsyncSession.
"""
from __future__ import annotations

from datetime import datetime, timezone

from neo4j import AsyncSession

from npc_engine.common.json_utils import dump_json, parse_json_list
from npc_engine.graph.gossip_write_queries import fetch_relation_log, update_relation_log


def _append_log(raw_log: str, tick_id: int, cause: str, trust_delta: int) -> str:
    payload = parse_json_list(raw_log)
    payload.append(
        {
            "tick_id": tick_id,
            "cause_id": cause,
            "deltas": {"trust": trust_delta, "fear": 0, "affection": 0},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    return dump_json(payload[-20:])


async def log_gossip(session: AsyncSession, src_id: str, dst_id: str, tick_id: int, trust_delta: int = 1) -> None:
    """Append a gossip interaction entry to the RELATES_TO delta log with optimistic retry.

    Uses an optimistic-concurrency pattern (compare-and-swap on delta_log) with up
    to 3 attempts before giving up silently. Missing edges are silently skipped.

    Args:
        session: Active Neo4j async session.
        src_id: Source character node ID (gossip sharer).
        dst_id: Destination character node ID (gossip receiver).
        tick_id: Current game tick for the log entry.
        trust_delta: Trust delta to apply; positive for truthful gossip, negative for distortion.
    """

    for _ in range(3):
        current_log = await fetch_relation_log(session, src_id=src_id, dst_id=dst_id)
        if current_log is None:
            return
        updated = _append_log(raw_log=current_log, tick_id=tick_id, cause="gossip", trust_delta=trust_delta)
        wrote = await update_relation_log(
            session,
            src_id=src_id,
            dst_id=dst_id,
            expected_delta_log=current_log,
            delta_log=updated,
            trust_delta=trust_delta,
        )
        if wrote:
            return
