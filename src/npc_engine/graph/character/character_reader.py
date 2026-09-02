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

# Strict, not forgiving: an absent `is_active` means NOT active (DEC-252 / ISSUE-258).
# `character.yaml` declares the field `required: true`, so a Character without it is
# already outside the contract, and every other is_active predicate in src/ is bare.
# A `coalesce(..., true)` here would silently repair a contract violation for this one
# reader while 36 others treat the same node as deleted.
CYPHER_GET_NPC_IDS = """
MATCH (c:Character)
WHERE c.is_player = false
  AND c.is_active = true
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
