"""
Module: rumor_trace_service
Layer: graph
Purpose: Query and mutate KNOWS_ABOUT edges for planted rumors — traces the NPC chain
         that received a fabricated event, and marks an edge as corrected so the NPC
         stops referencing the lie in dialogue.
Does NOT: propagate gossip or generate distortions — that is the gossip engine's job.
Dependencies injected: AsyncSession (caller-supplied).
Used by: npc_engine.api.routes.rumor_trace
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

_KNOWLEDGE_STATE_CORRECTED = "corrected"

CYPHER_TRACE_RUMOR_CHAIN = """
MATCH (npc:Character)-[k:KNOWS_ABOUT]->(e:Event {id: $event_id})
WHERE npc.is_active = true
RETURN npc.id AS npc_id,
       npc.name AS npc_name,
       k.knowledge_state AS knowledge_state,
       k.learned_at_tick AS learned_at_tick,
       k.distorted_summary AS distorted_summary
ORDER BY k.learned_at_tick ASC
"""

CYPHER_CORRECT_RUMOR = """
MATCH (npc:Character {id: $npc_id})-[k:KNOWS_ABOUT]->(e:Event {id: $event_id})
SET k.knowledge_state = $corrected_state
RETURN count(k) AS updated
"""


async def trace_rumor_chain(
    session: AsyncSession,
    event_id: str,
) -> list[dict[str, Any]]:
    """Return all NPCs that hold a KNOWS_ABOUT edge to event_id, oldest first.

    Ordered by learned_at_tick so the propagation path is visible: the first
    entry is the original recipient, subsequent entries are downstream holders.

    Args:
        session: Active Neo4j session.
        event_id: ID of the fabricated Event node to trace.

    Returns:
        List of dicts with ``npc_id``, ``npc_name``, ``knowledge_state``,
        ``learned_at_tick``, and ``distorted_summary`` (nullable).
        Empty list if the event has no KNOWS_ABOUT holders.
    """
    result = await session.run(CYPHER_TRACE_RUMOR_CHAIN, event_id=event_id)
    try:
        rows = [dict(record) async for record in result]
    finally:
        await result.consume()
    return rows


async def correct_rumor_at_npc(
    session: AsyncSession,
    npc_id: str,
    event_id: str,
) -> bool:
    """Mark the KNOWS_ABOUT edge for npc_id→event_id as 'corrected'.

    After correction, get_events_for_npc excludes this edge, so the NPC no
    longer references the lie in subsequent dialogue.  NPCs that have already
    propagated the rumor onward are unaffected — only npc_id is corrected.

    Args:
        session: Active Neo4j session.
        npc_id: NPC whose belief in the rumor should be corrected.
        event_id: ID of the fabricated Event node.

    Returns:
        True if the edge existed and was updated; False if no such edge.
    """
    result = await session.run(
        CYPHER_CORRECT_RUMOR,
        npc_id=npc_id,
        event_id=event_id,
        corrected_state=_KNOWLEDGE_STATE_CORRECTED,
    )
    record = await result.single()
    await result.consume()
    if record is None:
        return False
    return int(record["updated"]) > 0
