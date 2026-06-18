"""
Module: emotion_writer
Layer: graph
Purpose: Writes NPC emotion scalars to the character node in Neo4j via MERGE.
Does NOT: compute emotion values, call LLMs, manage transaction lifecycle,
          import from engine layer.
Dependencies: neo4j.AsyncSession
Dependencies injected: AsyncSession (per call — stateless, no constructor state).
Used by: engines/emotion/emotion_updater (optional DI).
"""

from __future__ import annotations

from neo4j import AsyncSession

_CYPHER_MERGE_EMOTION = """
MERGE (c:Character {id: $npc_id})
SET c.emotion_valence = $valence,
    c.emotion_arousal = $arousal,
    c.emotion_mood_label = $mood_label,
    c.emotion_updated_at_tick = $tick
"""


class EmotionGraphWriter:
    """Writes emotion state scalars to a Character node via MERGE Cypher.

    Stateless — safe to share across multiple EmotionUpdater instances.
    Does NOT open or commit transactions; the caller owns session lifecycle.
    """

    async def write_emotion(
        self,
        session: AsyncSession,
        npc_id: str,
        valence: int,
        arousal: int,
        label: str,
        tick: int,
    ) -> None:
        """Persist an NPC's emotion state to its Character node.

        Uses MERGE so the operation is idempotent regardless of whether the
        character node already has emotion fields.

        Args:
            session: Active Neo4j async session.
            npc_id: Unique identifier of the NPC / Character node.
            valence: Emotion valence in range [-100, 100].
            arousal: Emotion arousal in range [0, 100].
            label: Current mood label string (e.g. "neutral", "happy").
            tick: Current world-clock tick at which the update occurred.
        """
        result = await session.run(
            _CYPHER_MERGE_EMOTION,
            npc_id=npc_id,
            valence=valence,
            arousal=arousal,
            mood_label=label,
            tick=tick,
        )
        await result.consume()
