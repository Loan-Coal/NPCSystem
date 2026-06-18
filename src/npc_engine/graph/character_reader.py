"""
Module: character_reader
Layer: graph
Purpose: Read-only Cypher accessor for Character nodes.
         Provides get_npc_ids() to fetch all active non-player character IDs —
         used by reputation and other tick-scheduler adapters that need the full
         NPC roster without importing from the engines layer.
Does NOT: write to the graph, manage transactions, or derive higher-level models.
Dependencies: neo4j.AsyncSession
Dependencies injected: AsyncSession (per call — stateless, no constructor).
Used by: engines.reputation.reputation_tick_adapter
"""

from __future__ import annotations

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

CYPHER_GET_NPC_IDS = """
MATCH (c:Character)
WHERE c.is_player = false
  AND coalesce(c.is_active, true) = true
RETURN c.id AS character_id
"""


async def get_npc_ids(session: AsyncSession) -> list[str]:
    """Return the IDs of all active non-player Characters in the graph.

    Used by the reputation tick adapter to supply npc_ids to ReputationEngine.run_tick.

    Args:
        session: Active Neo4j async session.

    Returns:
        List of character ID strings; empty list if none exist.
    """
    result = await session.run(CYPHER_GET_NPC_IDS)
    try:
        ids: list[str] = [record["character_id"] async for record in result]
    finally:
        await result.consume()
    return ids
