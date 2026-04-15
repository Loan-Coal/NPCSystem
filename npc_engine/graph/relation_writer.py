"""
relation_writer.py - Applies RELATES_TO updates with bounded relation values.

Does NOT: validate window constraints.

Dependencies injected: AsyncManagedTransaction.
"""

from neo4j import AsyncTransaction

from utils.errors import RelationEdgeNotFoundError


CYPHER_GET_RELATION_VALUES = """
MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id})
RETURN r.trust AS trust, r.fear AS fear, r.affection AS affection
"""

CYPHER_SET_RELATION_VALUES = """
MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id})
SET r.trust = $new_trust,
    r.fear = $new_fear,
    r.affection = $new_affection,
    r.interaction_count = coalesce(r.interaction_count, 0) + 1,
    r.last_updated_at = datetime()
"""


async def get_relation_values(tx: AsyncTransaction, src_id: str, dst_id: str) -> dict[str, int]:
    """Fetch current relation values for one directed edge."""

    result = await tx.run(CYPHER_GET_RELATION_VALUES, src_id=src_id, dst_id=dst_id)
    record = await result.single()
    if record is None:
        raise RelationEdgeNotFoundError(src_id=src_id, dst_id=dst_id)
    return {"trust": int(record["trust"]), "fear": int(record["fear"]), "affection": int(record["affection"])}


async def set_relation_values(
    tx: AsyncTransaction,
    src_id: str,
    dst_id: str,
    new_values: dict[str, int],
) -> None:
    """Persist clamped relation values for one directed edge."""

    result = await tx.run(
        CYPHER_SET_RELATION_VALUES,
        src_id=src_id,
        dst_id=dst_id,
        new_trust=new_values["trust"],
        new_fear=new_values["fear"],
        new_affection=new_values["affection"],
    )
    summary = await result.consume()
    if summary.counters.properties_set == 0:
        raise RelationEdgeNotFoundError(src_id=src_id, dst_id=dst_id)
