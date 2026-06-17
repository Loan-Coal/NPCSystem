"""
Module: trust_queries
Layer: graph
Purpose: Read-only Neo4j queries for NPC trust relationships used by the retrieval layer.
Does NOT: mutate graph state or call LLM services.
Dependencies injected: AsyncSession (caller-managed).
Used by: retrieval.context_builder
"""

from __future__ import annotations

from typing import Any
from neo4j import AsyncSession


async def get_trust_scores_for_events(
    session: AsyncSession,
    npc_id: str,
    event_ids: list[str],
) -> dict[str, float]:
    """Return normalized trust (0–1) from npc toward the actor of each event.

    For each event in event_ids, looks up the RELATES_TO.trust from npc to the
    event's actor_id and normalizes to [0, 1]. Events with no actor or no
    RELATES_TO edge are omitted from the result.

    Args:
        session: Active Neo4j async session.
        npc_id: ID of the NPC whose trust perspective is used.
        event_ids: IDs of events to score.

    Returns:
        Dict mapping event_id → normalized trust score (0–1).
    """

    if not event_ids:
        return {}

    query = """
    UNWIND $event_ids AS eid
    MATCH (e:Event {id: eid})
    WHERE e.actor_id IS NOT NULL
    MATCH (npc:Character {id: $npc_id})-[r:RELATES_TO]->(actor:Character {id: e.actor_id})
    RETURN eid AS event_id, toFloat(r.trust) / 100.0 AS trust_score
    """
    result = await session.run(query, event_ids=event_ids, npc_id=npc_id)
    records = await result.data()
    return {
        row["event_id"]: max(0.0, min(1.0, float(row["trust_score"])))
        for row in records
        if row["trust_score"] is not None
    }


async def get_second_hop_events(
    session: AsyncSession,
    npc_id: str,
    trust_threshold: int = 50,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return events that trusted friends KNOW_ABOUT but the NPC does not.

    Traverses one hop via RELATES_TO edges with trust >= trust_threshold to find
    events known to friends but not to the NPC. Ordered by descending trust then
    descending recency.

    Args:
        session: Active Neo4j async session.
        npc_id: ID of the NPC to build second-hop events for.
        trust_threshold: Minimum RELATES_TO.trust score (0–100) to consider a friend.
        limit: Maximum number of second-hop events to return.

    Returns:
        List of event property dicts, each augmented with a 'trust_weight' key.
    """

    query = """
    MATCH (npc:Character {id: $npc_id})-[r:RELATES_TO]->(friend:Character)
    WHERE r.trust >= $trust_threshold
    MATCH (friend)-[:KNOWS_ABOUT]->(e:Event)
    WHERE NOT (npc)-[:KNOWS_ABOUT]->(e)
    RETURN DISTINCT e, r.trust AS trust_weight
    ORDER BY trust_weight DESC, e.occurred_at DESC
    LIMIT $limit
    """
    result = await session.run(
        query,
        npc_id=npc_id,
        trust_threshold=trust_threshold,
        limit=limit,
    )
    records = await result.data()
    events = []
    for row in records:
        evt = dict(row["e"])
        evt["trust_weight"] = int(row["trust_weight"])
        events.append(evt)
    return events
