"""
Module: emotion_bootstrap
Layer: engines
Purpose: Seeds EmotionStore from persisted character-node emotion fields at boot.
         Reads graph emotion data via the injected EmotionBootstrapGraphPort and
         hydrates the in-memory store so emotion state survives process restarts.
Does NOT: write to the graph, compute emotion arithmetic, call LLMs, or open sessions.
Dependencies injected: EmotionBootstrapGraphPort (per call), EmotionStore (per call).
Used by: main.py lifespan (wired via Neo4jEmotionBootstrapRepository).
"""

from __future__ import annotations

from npc_engine.engines.emotion.emotion_state import EmotionState
from npc_engine.engines.emotion.emotion_store import EmotionStore
from npc_engine.engines.ports.emotion_bootstrap_port import EmotionBootstrapGraphPort

_DEFAULT_LABEL = "neutral"


class EmotionBootstrapper:
    """Reads persisted emotion fields from the graph port and seeds an EmotionStore.

    Stateless — safe to instantiate once and call multiple times.
    """

    async def load_from_graph(
        self,
        port: EmotionBootstrapGraphPort,
        store: EmotionStore,
        npc_ids: list[str],
    ) -> None:
        """Seed the store with emotion state read from character nodes.

        For each NPC ID: if the character node has all four emotion fields set,
        the store is populated with those values.  If any field is missing/None,
        that NPC is left at the store's default neutral state.

        Args:
            port: EmotionBootstrapGraphPort for reading persisted emotion fields.
            store: In-memory emotion store to populate.
            npc_ids: List of NPC IDs to bootstrap.
        """
        for npc_id in npc_ids:
            state = await self._read_one(port=port, npc_id=npc_id)
            if state is not None:
                await store.set(npc_id=npc_id, state=state)

    async def _read_one(self, port: EmotionBootstrapGraphPort, npc_id: str) -> EmotionState | None:
        fields = await port.get_emotion_fields(npc_id)
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
