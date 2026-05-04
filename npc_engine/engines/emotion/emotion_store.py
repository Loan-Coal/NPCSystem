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
        """Return stored emotion state or a neutral default for unknown NPCs.

        Args:
            npc_id: Unique identifier of the NPC.

        Returns:
            Stored EmotionState if present, otherwise a default neutral EmotionState.
        """
        return self._states.get(npc_id, EmotionState())

    def set(self, npc_id: str, state: EmotionState) -> None:
        """Replace the stored emotion state for an NPC (immutable update).

        Args:
            npc_id: Unique identifier of the NPC.
            state: New EmotionState to store.
        """
        self._states = {
            **self._states,
            npc_id: state,
        }
