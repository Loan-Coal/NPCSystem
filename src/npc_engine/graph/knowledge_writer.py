"""
Module: knowledge_writer
Layer: graph
Purpose: Writes learned-fact belief nodes and provenance-annotated BELIEVES edges.
Does NOT: contain engine logic, call LLMs, or validate facts — validation is in KnowledgeExtractionEngine.
Dependencies: neo4j.AsyncSession, stdlib hashlib.
Dependencies injected: AsyncSession (per call).
Used by: engines.knowledge_learning.knowledge_extraction_engine, engines.deception.deception_engine
"""

from __future__ import annotations

import hashlib

from neo4j import AsyncSession, AsyncTransaction

from npc_engine.graph.transaction_coordinator import run_in_tx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Length of the truncated SHA-256 hex digest used as the stable belief id (ISSUE-089).
_BELIEF_ID_HASH_LENGTH = 16

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
    r.confidence          = $confidence,
    r.is_deception        = $is_deception,
    r.deception_goal_id   = $deception_goal_id
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
    is_deception: bool = False,
    deception_goal_id: str | None = None,
) -> str:
    """Merge a Belief node and create/update the BELIEVES edge with provenance fields.

    Dedups by a stable (npc_id, content) hash. DEC-072 provenance + optional deception
    fields (DEC-103/EXP-228, default False/None — back-compat for existing callers) are
    written on the edge. Returns the stable belief id (truncated SHA-256 of npc_id:content).
    """
    belief_id = hashlib.sha256(f"{npc_id}:{content}".encode()).hexdigest()[:_BELIEF_ID_HASH_LENGTH]

    async def _work(tx: AsyncTransaction) -> None:
        await tx.run(
            _CYPHER_WRITE_BELIEF_WITH_PROVENANCE,
            belief_id=belief_id,
            content=content,
            confidence=confidence,
            game_time_str=game_time_str,
            npc_id=npc_id,
            source_character_id=source_character_id,
            learned_at_tick=learned_at_tick,
            is_deception=is_deception,
            deception_goal_id=deception_goal_id,
        )

    await run_in_tx(session, _work)
    return belief_id
