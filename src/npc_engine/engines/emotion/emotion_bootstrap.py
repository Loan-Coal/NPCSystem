"""
Module: emotion_bootstrap
Layer: engines
Purpose: Seeds EmotionStore from persisted character-node emotion fields at boot.
         Reads Neo4j character nodes and hydrates the in-memory store so emotion
         state survives process restarts.
Does NOT: write to the graph, compute emotion arithmetic, call LLMs, or run Cypher directly.
Dependencies: neo4j.AsyncSession, engines/emotion/emotion_store,
              engines/emotion/emotion_state, graph/emotion_reader
Dependencies injected: AsyncSession (per call), EmotionStore (per call).
Used by: main.py lifespan (slice-2 wiring — not yet connected).
"""

from __future__ import annotations

from neo4j import AsyncSession

from npc_engine.engines.emotion.emotion_state import EmotionState
from npc_engine.engines.emotion.emotion_store import EmotionStore
from npc_engine.graph.emotion_reader import get_emotion_fields

_DEFAULT_LABEL = "neutral"


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

    async def _read_one(self, session: AsyncSession, npc_id: str) -> EmotionState | None:
        fields = await get_emotion_fields(session, npc_id)
        if fields is None:
            return None
        valence = fields.get("emotion_valence")
        arousal = fields.get("emotion_arousal")
        label = fields.get("emotion_mood_label")
        if valence is None or arousal is None:
            return None
        return EmotionState(
            valence=int(valence),
            arousal=int(arousal),
            label=label if label is not None else _DEFAULT_LABEL,
        )
