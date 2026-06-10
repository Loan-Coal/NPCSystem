"""
Module: emotion_bootstrap
Layer: engines
Purpose: Seeds EmotionStore from persisted character-node emotion fields at boot.
         Reads Neo4j character nodes and hydrates the in-memory store so emotion
         state survives process restarts.
Does NOT: write to the graph, compute emotion arithmetic, call LLMs.
Dependencies: neo4j.AsyncSession, engines/emotion/emotion_store,
              engines/emotion/emotion_state
Dependencies injected: AsyncSession (per call), EmotionStore (per call).
Used by: main.py lifespan (slice-2 wiring — not yet connected).
"""

from __future__ import annotations

from neo4j import AsyncSession

from npc_engine.engines.emotion.emotion_state import EmotionState
from npc_engine.engines.emotion.emotion_store import EmotionStore

# ---------------------------------------------------------------------------
# Cypher constants
# ---------------------------------------------------------------------------

CYPHER_READ_EMOTION = """
MATCH (c:Character {id: $npc_id})
RETURN c.emotion_valence          AS emotion_valence,
       c.emotion_arousal          AS emotion_arousal,
       c.emotion_mood_label       AS emotion_mood_label,
       c.emotion_updated_at_tick  AS emotion_updated_at_tick
"""

_DEFAULT_LABEL = "neutral"
_DEFAULT_VALENCE = 0
_DEFAULT_AROUSAL = 0


class EmotionBootstrapper:
    """Reads persisted emotion fields from Neo4j and seeds an EmotionStore.

    Stateless — safe to instantiate once and call multiple times.
    """

    async def load_from_graph(
        self,
        session: AsyncSession,
        store: EmotionStore,
        npc_ids: list[str],
    ) -> None:
        """Seed the store with emotion state read from character nodes.

        For each NPC ID: if the character node has all four emotion fields set,
        the store is populated with those values.  If any field is missing/None,
        that NPC is left at the store's default neutral state.

        Args:
            session: Active Neo4j async session.
            store: In-memory emotion store to populate.
            npc_ids: List of NPC IDs to bootstrap.
        """
        for npc_id in npc_ids:
            state = await self._read_one(session=session, npc_id=npc_id)
            if state is not None:
                await store.set(npc_id=npc_id, state=state)

    async def _read_one(
        self,
        session: AsyncSession,
        npc_id: str,
    ) -> EmotionState | None:
        """Read emotion fields for a single NPC from the graph.

        Returns None if the node has no persisted emotion data (all fields null).

        Args:
            session: Active Neo4j async session.
            npc_id: Unique identifier of the NPC.

        Returns:
            EmotionState hydrated from the graph, or None if no data found.
        """
        result = await session.run(CYPHER_READ_EMOTION, npc_id=npc_id)
        try:
            record = None
            async for row in result:
                record = row
                break
        finally:
            await result.consume()

        if record is None:
            return None

        valence = record["emotion_valence"]
        arousal = record["emotion_arousal"]
        label = record["emotion_mood_label"]

        if valence is None or arousal is None:
            return None

        return EmotionState(
            valence=int(valence),
            arousal=int(arousal),
            label=label if label is not None else _DEFAULT_LABEL,
        )
