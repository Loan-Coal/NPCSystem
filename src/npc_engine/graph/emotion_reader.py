"""
Module: emotion_reader
Layer: graph
Purpose: Read-only Cypher queries for emotion fields persisted on character nodes (EXP-14).
Does NOT: write to the graph, call LLMs, or import engine-layer code.
Dependencies: neo4j.AsyncSession
Dependencies injected: None (pure Cypher, session passed per call).
Used by: engines/emotion/emotion_bootstrap
"""
from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

_CYPHER_READ_EMOTION = """
MATCH (c:Character {id: $npc_id})
RETURN c.emotion_valence          AS emotion_valence,
       c.emotion_arousal          AS emotion_arousal,
       c.emotion_mood_label       AS emotion_mood_label,
       c.emotion_updated_at_tick  AS emotion_updated_at_tick
"""


async def get_emotion_fields(session: AsyncSession, npc_id: str) -> dict[str, Any] | None:
    """Fetch persisted emotion fields from a character node.

    Args:
        session: Active Neo4j async session.
        npc_id: Unique identifier of the NPC.

    Returns:
        Dict with keys emotion_valence, emotion_arousal, emotion_mood_label,
        emotion_updated_at_tick — all may be None if not yet persisted.
        Returns None if the character node does not exist.
    """
    result = await session.run(_CYPHER_READ_EMOTION, npc_id=npc_id)
    try:
        record = None
        async for row in result:
            record = row
            break
    finally:
        await result.consume()
    if record is None:
        return None
    return {
        "emotion_valence": record["emotion_valence"],
        "emotion_arousal": record["emotion_arousal"],
        "emotion_mood_label": record["emotion_mood_label"],
        "emotion_updated_at_tick": record["emotion_updated_at_tick"],
    }
