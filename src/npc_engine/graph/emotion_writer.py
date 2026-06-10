"""
Module: emotion_writer
Layer: graph
Purpose: Writes NPC emotion scalars to the character node in Neo4j via MERGE.
Does NOT: compute emotion values, call LLMs, manage transaction lifecycle.
Dependencies: neo4j.AsyncSession, engines/emotion/emotion_state (EmotionState only).
Used by: engines/emotion/emotion_updater (optional DI).
Dependencies injected: AsyncSession (per call — stateless, no constructor state).
"""

from __future__ import annotations

from neo4j import AsyncSession

from npc_engine.engines.emotion.emotion_state import EmotionState

# ---------------------------------------------------------------------------
# Cypher constants — no raw strings in method bodies
# ---------------------------------------------------------------------------

CYPHER_MERGE_EMOTION = """
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
        state: EmotionState,
        tick: int,
    ) -> None:
        """Persist an NPC's emotion state to its Character node.

        Uses MERGE so the operation is idempotent regardless of whether the
        character node already has emotion fields.

        Args:
            session: Active Neo4j async session.
            npc_id: Unique identifier of the NPC / Character node.
            state: The new emotion state to persist.
            tick: Current world-clock tick at which the update occurred.
        """
        result = await session.run(
            CYPHER_MERGE_EMOTION,
            npc_id=npc_id,
            valence=state.valence,
            arousal=state.arousal,
            mood_label=state.label,
            tick=tick,
        )
        await result.consume()
