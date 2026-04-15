"""
emotion_store.py - In-memory store for NPC emotion state.

Does NOT: synchronize state to external systems.

Dependencies injected: None.
"""

from engines.emotion.emotion_state import EmotionState


class EmotionStore:
    """Simple in-memory emotion state store keyed by NPC id."""

    def __init__(self) -> None:
        self._states: dict[str, EmotionState] = {}

    def get(self, npc_id: str) -> EmotionState:
        """Return stored state or neutral default."""

        return self._states.get(npc_id, EmotionState())

    def set(self, npc_id: str, state: EmotionState) -> None:
        """Persist state for NPC id."""

        self._states = {
            **self._states,
            npc_id: state,
        }
