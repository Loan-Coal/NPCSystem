"""
Module: emotion_store
Layer: engines
Purpose: Async-safe in-memory store for NPC emotion state, protected by asyncio.Lock.
Does NOT: synchronize state to external systems.
Dependencies: engines/emotion/emotion_state
Dependencies injected: None.
Used by: engines/emotion/emotion_updater, engines/mood/mood_contagion_engine, api/routes/npc_state
"""

from __future__ import annotations

import asyncio

from npc_engine.engines.emotion.emotion_state import EmotionState


class EmotionStore:
    """Async-safe in-memory emotion state store keyed by NPC id.

    All public methods acquire ``_lock`` before reading or writing ``_states``
    to prevent lost updates across awaits in concurrent async handlers
    (DialogueHandler, GossipHandler.apply_event_shock, MoodContagionEngine).
    """

    def __init__(self) -> None:
        self._states: dict[str, EmotionState] = {}
        self._lock = asyncio.Lock()

    async def get(self, npc_id: str) -> EmotionState:
        """Return stored emotion state or a neutral default for unknown NPCs.

        Args:
            npc_id: Unique identifier of the NPC.

        Returns:
            Stored EmotionState if present, otherwise a default neutral EmotionState.
        """
        async with self._lock:
            return self._states.get(npc_id, EmotionState())

    async def set(self, npc_id: str, state: EmotionState) -> None:
        """Replace the stored emotion state for an NPC (immutable update).

        Args:
            npc_id: Unique identifier of the NPC.
            state: New EmotionState to store.
        """
        async with self._lock:
            self._states = {
                **self._states,
                npc_id: state,
            }
