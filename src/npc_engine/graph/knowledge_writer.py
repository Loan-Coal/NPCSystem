"""
Module: knowledge_writer
Layer: graph
Purpose: Writes learned-fact belief nodes and provenance-annotated BELIEVES edges.
Dependencies: None (Cypher only; uuid from stdlib).
Used by: engines.knowledge_learning.knowledge_extraction_engine
"""

from __future__ import annotations

import uuid

from neo4j import AsyncSession

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

_CYPHER_WRITE_BELIEF_WITH_PROVENANCE = """
MERGE (b:Belief {id: $belief_id})
SET b.content              = $content,
    b.confidence           = $confidence,
    b.created_at_game_time = $game_time_str
WITH b
MATCH (c:Character {id: $npc_id})
MERGE (c)-[r:BELIEVES]->(b)
SET r.source_character_id = $source_character_id,
    r.learned_at_tick     = $learned_at_tick,
    r.confidence          = $confidence
RETURN b.id AS belief_id
"""


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


async def write_belief(
    session: AsyncSession,
    *,
    npc_id: str,
    content: str,
    confidence: int,
    source_character_id: str,
    learned_at_tick: int,
    game_time_str: str,
) -> str:
    """Merge a Belief node and create/update the BELIEVES edge with provenance fields.

    Opens a single transaction, merges the belief by generated UUID, creates or
    updates the BELIEVES edge from the NPC character node, and commits.

    Args:
        session: Active Neo4j async session.
        npc_id: ID of the NPC character node who holds the belief.
        content: Freeform text of the learned fact.
        confidence: Confidence level (0–100); stored on both node and edge.
        source_character_id: ID of the character who stated the fact (provenance).
        learned_at_tick: Game tick at which the fact was learned (provenance).
        game_time_str: Human-readable game-time string stored on the belief node.

    Returns:
        Generated UUID string for the new or merged belief node.
    """
    belief_id = str(uuid.uuid4())
    tx = await session.begin_transaction()
    async with tx:
        await tx.run(
            _CYPHER_WRITE_BELIEF_WITH_PROVENANCE,
            belief_id=belief_id,
            content=content,
            confidence=confidence,
            game_time_str=game_time_str,
            npc_id=npc_id,
            source_character_id=source_character_id,
            learned_at_tick=learned_at_tick,
        )
    return belief_id
