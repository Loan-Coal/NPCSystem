"""
delta_log_writer.py - Persists relation edge delta logs in Neo4j.

Does NOT: validate relation bounds.

Dependencies injected: AsyncManagedTransaction.
"""

import json

from neo4j import AsyncTransaction


CYPHER_SET_RELATION_DELTA_LOG = """
MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id})
SET r.delta_log = $new_delta_log,
    r.last_updated_at = datetime()
"""


async def write_delta_log(
    tx: AsyncTransaction,
    src_id: str,
    dst_id: str,
    delta_log_payload: list[dict],
) -> None:
    """Persist serialized delta log on relation edge."""

    serialized_delta_log = json.dumps(delta_log_payload)
    await tx.run(
        CYPHER_SET_RELATION_DELTA_LOG,
        src_id=src_id,
        dst_id=dst_id,
        new_delta_log=serialized_delta_log,
    )
