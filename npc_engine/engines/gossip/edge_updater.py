"""
edge_updater.py - Appends gossip interaction metadata to relation delta logs.

Does NOT: enforce mutation bounds.

Dependencies injected: AsyncSession.
"""

from datetime import datetime, timezone

from neo4j import AsyncSession

from common.json_utils import dump_json, parse_json_list


CYPHER_GET_RELATION_LOG = """
MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id})
RETURN coalesce(r.delta_log, '[]') AS delta_log
"""

CYPHER_SET_RELATION_LOG = """
MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id})
WHERE coalesce(r.delta_log, '[]') = $expected_delta_log
SET r.delta_log = $delta_log,
        r.trust = CASE
            WHEN coalesce(r.trust, 50) + $trust_delta > 100 THEN 100
            WHEN coalesce(r.trust, 50) + $trust_delta < 0 THEN 0
            ELSE coalesce(r.trust, 50) + $trust_delta
        END,
    r.last_updated_at = datetime()
RETURN 1 AS updated
"""


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
    """Append gossip metadata to relation edge delta log."""

    for _ in range(3):
        result = await session.run(CYPHER_GET_RELATION_LOG, src_id=src_id, dst_id=dst_id)
        record = await result.single()
        if record is None:
            return
        current_log = str(record["delta_log"])
        updated = _append_log(raw_log=current_log, tick_id=tick_id, cause="gossip", trust_delta=trust_delta)
        write_result = await session.run(
            CYPHER_SET_RELATION_LOG,
            src_id=src_id,
            dst_id=dst_id,
            expected_delta_log=current_log,
            delta_log=updated,
            trust_delta=trust_delta,
        )
        write_row = await write_result.single()
        if write_row is not None:
            return
