"""
Module: gossip_write_queries
Layer: graph
Purpose: Write-side Cypher for gossip — knowledge propagation, secret propagation,
         and relation-log optimistic CAS writes.
Does NOT: open transactions; each function accepts an AsyncSession from the caller.
Dependencies injected: AsyncSession (passed per call)
Dependencies: neo4j, graph.labels, graph.relationships
Used by: engines/gossip/knowledge_propagator, engines/gossip/edge_updater
"""
from __future__ import annotations

from neo4j import AsyncSession

from npc_engine.graph.labels import CHARACTER, EVENT, SECRET
from npc_engine.graph.relationships import KNOWS_ABOUT, KNOWS_SECRET, RELATES_TO

# ---------------------------------------------------------------------------
# Query constants
# ---------------------------------------------------------------------------

CYPHER_PROPAGATE_KNOWLEDGE = f"""
MATCH (receiver:{CHARACTER} {{id: $receiver_id}}), (event:{EVENT} {{id: $event_id}})
MERGE (receiver)-[k:{KNOWS_ABOUT}]->(event)
SET k.knowledge_state = $knowledge_state,
    k.distortion_type = $distortion_type,
    k.distortion_level = $distortion_level,
    k.distorted_summary = $distorted_summary,
    k.learned_at_tick = $tick_id,
    k.source_character_id = $source_character_id
"""

CYPHER_PROPAGATE_SECRET = f"""
MATCH (receiver:{CHARACTER} {{id: $receiver_id}}), (secret:{SECRET} {{id: $secret_id}})
MERGE (receiver)-[k:{KNOWS_SECRET}]->(secret)
SET k.knowledge_state = $knowledge_state,
    k.learned_at_tick = $tick_id,
    k.source_character_id = $source_character_id
"""

CYPHER_GET_RELATION_LOG = f"""
MATCH (a:{CHARACTER} {{id: $src_id}})-[r:{RELATES_TO}]->(b:{CHARACTER} {{id: $dst_id}})
RETURN coalesce(r.delta_log, '[]') AS delta_log
"""

CYPHER_SET_RELATION_LOG = f"""
MATCH (a:{CHARACTER} {{id: $src_id}})-[r:{RELATES_TO}]->(b:{CHARACTER} {{id: $dst_id}})
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

# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------


async def write_knowledge_propagation(
    session: AsyncSession,
    receiver_id: str,
    event_id: str,
    knowledge_state: str,
    distortion_type: str | None,
    distortion_level: float,
    distorted_summary: str,
    tick_id: int,
    source_character_id: str,
) -> None:
    """Merge a KNOWS_ABOUT edge from receiver to event with full distortion metadata.

    Args:
        session: Active Neo4j async session.
        receiver_id: Character node ID receiving the knowledge.
        event_id: Event node ID being propagated.
        knowledge_state: "knows" or "rumor".
        distortion_type: Distortion label, or None for clean propagation.
        distortion_level: Float distortion magnitude.
        distorted_summary: Possibly distorted event summary.
        tick_id: Current game tick.
        source_character_id: Character node ID that shared the knowledge.
    """
    await session.run(
        CYPHER_PROPAGATE_KNOWLEDGE,
        receiver_id=receiver_id,
        event_id=event_id,
        knowledge_state=knowledge_state,
        distortion_type=distortion_type,
        distortion_level=distortion_level,
        distorted_summary=distorted_summary,
        tick_id=tick_id,
        source_character_id=source_character_id,
    )


async def write_secret_propagation(
    session: AsyncSession,
    receiver_id: str,
    secret_id: str,
    source_character_id: str,
    tick_id: int,
    knowledge_state: str,
) -> None:
    """Merge a KNOWS_SECRET edge from receiver to secret.

    Args:
        session: Active Neo4j async session.
        receiver_id: Character node ID receiving the secret.
        secret_id: Secret node ID being propagated.
        source_character_id: Character node ID sharing the secret.
        tick_id: Current game tick.
        knowledge_state: "knows" or "rumor".
    """
    await session.run(
        CYPHER_PROPAGATE_SECRET,
        receiver_id=receiver_id,
        secret_id=secret_id,
        knowledge_state=knowledge_state,
        tick_id=tick_id,
        source_character_id=source_character_id,
    )


async def fetch_relation_log(
    session: AsyncSession, src_id: str, dst_id: str
) -> str | None:
    """Return the raw delta_log JSON string on the RELATES_TO edge, or None if no edge.

    Args:
        session: Active Neo4j async session.
        src_id: Source character node ID.
        dst_id: Destination character node ID.

    Returns:
        Raw JSON string (defaulting to '[]'), or None when no edge exists.
    """
    result = await session.run(CYPHER_GET_RELATION_LOG, src_id=src_id, dst_id=dst_id)
    record = await result.single()
    return str(record["delta_log"]) if record is not None else None


async def update_relation_log(
    session: AsyncSession,
    src_id: str,
    dst_id: str,
    expected_delta_log: str,
    delta_log: str,
    trust_delta: int,
) -> bool:
    """CAS-write the delta log and trust on the RELATES_TO edge.

    Uses optimistic concurrency: only updates if the current delta_log matches
    expected_delta_log. Returns True when the write succeeded, False on conflict.

    Args:
        session: Active Neo4j async session.
        src_id: Source character node ID.
        dst_id: Destination character node ID.
        expected_delta_log: The log value read in the prior fetch (CAS guard).
        delta_log: New serialized log to store.
        trust_delta: Trust delta to apply (clamped to [0, 100]).

    Returns:
        True if the write was applied, False if the CAS guard failed.
    """
    result = await session.run(
        CYPHER_SET_RELATION_LOG,
        src_id=src_id,
        dst_id=dst_id,
        expected_delta_log=expected_delta_log,
        delta_log=delta_log,
        trust_delta=trust_delta,
    )
    record = await result.single()
    return record is not None
