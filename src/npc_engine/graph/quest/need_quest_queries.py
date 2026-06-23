"""
Module: need_quest_queries
Layer: graph
Purpose: Read-only Cypher queries for NeedQuestTrigger idempotency checks.
         Determines whether an NPC already has an outstanding draft quest
         so the trigger can skip duplicate generation.
Does NOT: write to the graph, call LLMs, or import engine-layer code.
Dependencies: None (pure Cypher constants, session passed per call).
Dependencies injected: AsyncSession (passed per call).
Used by: npc_engine.engines.quest_generation.need_quest_trigger
"""

from __future__ import annotations

from neo4j import AsyncSession

CYPHER_HAS_DRAFT_QUEST = """
MATCH (c:Character {id: $character_id})-[:HAS_QUEST]->(q:Quest)
WHERE q.status = 'draft'
RETURN q.id AS quest_id
LIMIT 1
"""


async def has_draft_quest(
    session: AsyncSession,
    character_id: str,
) -> bool:
    """Return True if the character already has at least one quest with status='draft'.

    Used as the idempotency guard in NeedQuestTrigger: if an NPC already has a
    pending draft quest, a new need-driven quest is not generated until the
    existing draft is resolved.

    Args:
        session: Active Neo4j async session.
        character_id: ID of the Character node to check.

    Returns:
        True if a draft quest exists for this character, False otherwise.
    """
    result = await session.run(CYPHER_HAS_DRAFT_QUEST, character_id=character_id)
    rows = [dict(r) async for r in result]
    await result.consume()
    return len(rows) > 0
