"""
Module: gossip_batch_queries
Layer: graph
Purpose: Batched Cypher queries for gossip tick processing — reduces N+1 round-trips
         to 2 session.run calls per tick (one read, one write).
Does NOT: open transactions; each function accepts an AsyncSession from the caller.
Dependencies injected: AsyncSession (passed per call)
Dependencies: neo4j
Used by: engines/gossip/gossip_handler
"""
from __future__ import annotations

from typing import Any

# Node label and relationship constants (inlined to avoid import from sibling
# modules that may not exist in all worktree configurations).
_CHARACTER = "Character"
_EVENT = "Event"
_SECRET = "Secret"
_KNOWS_ABOUT = "KNOWS_ABOUT"
_KNOWS_SECRET = "KNOWS_SECRET"
_RELATES_TO = "RELATES_TO"


# ---------------------------------------------------------------------------
# Batch read: event + trust for all pairs in one query
# ---------------------------------------------------------------------------

CYPHER_BATCH_EVENT_TRUST = f"""
UNWIND $pairs AS pair
MATCH (a:{_CHARACTER} {{id: pair.sharer_id}})-[k:{_KNOWS_ABOUT}]->(e:{_EVENT})
WHERE coalesce(k.knowledge_state, '') <> 'corrected'
WITH pair, a, e,
     coalesce(e.is_canonical, false) AS is_canonical,
     e.occurred_at AS occurred_at
ORDER BY pair.sharer_id, is_canonical DESC, occurred_at DESC
WITH pair, head(collect(e)) AS best_event,
     head(collect(is_canonical)) AS best_is_canonical
OPTIONAL MATCH (a2:{_CHARACTER} {{id: pair.sharer_id}})-[r:{_RELATES_TO}]->(b:{_CHARACTER} {{id: pair.receiver_id}})
RETURN pair.sharer_id  AS sharer_id,
       pair.receiver_id AS receiver_id,
       best_event.id    AS event_id,
       best_event.summary   AS summary,
       best_event.severity  AS severity,
       best_is_canonical    AS is_canonical,
       coalesce(r.trust, 50) AS trust
"""

# ---------------------------------------------------------------------------
# Batch write: propagate knowledge for all pairs in one UNWIND MERGE
# ---------------------------------------------------------------------------

CYPHER_BATCH_PROPAGATE_KNOWLEDGE = f"""
UNWIND $writes AS w
MATCH (receiver:{_CHARACTER} {{id: w.receiver_id}}), (event:{_EVENT} {{id: w.event_id}})
MERGE (receiver)-[k:{_KNOWS_ABOUT}]->(event)
SET k.knowledge_state = w.knowledge_state,
    k.distortion_type = w.distortion_type,
    k.distortion_level = w.distortion_level,
    k.distorted_summary = w.distorted_summary,
    k.learned_at_tick = w.tick_id,
    k.source_character_id = w.source_character_id
"""

# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------


CYPHER_SELECT_SECRET = f"""
MATCH (a:{_CHARACTER} {{id: $sharer_id}})-[:{_KNOWS_SECRET}]->(s:{_SECRET})
RETURN s.id AS secret_id, s.severity AS severity
ORDER BY s.severity DESC
LIMIT 1
"""


async def select_gossip_secret(session: Any, sharer_id: str) -> dict | None:
    """Return the most severe secret the sharer holds, or None.

    Args:
        session: Active Neo4j async session.
        sharer_id: Character node ID of the gossip sharer.

    Returns:
        Dict with keys secret_id and severity, or None.
    """
    result = await session.run(CYPHER_SELECT_SECRET, sharer_id=sharer_id)
    record = await result.single()
    if record is None:
        return None
    return dict(record)


async def select_batch_event_trust(
    session: Any,
    pairs: list[dict[str, str]],
) -> list[dict]:
    """Fetch event and trust data for all pairs in a single query.

    For each pair that has at least one qualifying event, returns one row with
    the best event plus the trust value between sharer and receiver.
    Pairs with no qualifying event produce no row.

    Args:
        session: Active Neo4j async session.
        pairs: List of dicts with keys ``sharer_id`` and ``receiver_id``.

    Returns:
        List of dicts with keys sharer_id, receiver_id, event_id, summary,
        severity, is_canonical, trust.
    """
    if not pairs:
        return []
    result = await session.run(CYPHER_BATCH_EVENT_TRUST, pairs=pairs)
    rows: list[dict] = []
    async for record in result:
        rows.append(dict(record))
    return rows


async def write_batch_knowledge_propagation(
    session: Any,
    writes: list[dict],
) -> None:
    """Merge KNOWS_ABOUT edges for multiple receiver/event pairs in one query.

    Each element of ``writes`` must have keys:
    receiver_id, event_id, knowledge_state, distortion_type, distortion_level,
    distorted_summary, tick_id, source_character_id.

    No-op when ``writes`` is empty.

    Args:
        session: Active Neo4j async session.
        writes: List of propagation parameter dicts, one per pair.
    """
    if not writes:
        return
    result = await session.run(CYPHER_BATCH_PROPAGATE_KNOWLEDGE, writes=writes)
    await result.consume()
