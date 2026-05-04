"""
emotion_updater.py - Applies mood updates and decay rules to emotion states.

Does NOT: read or write graph data.

Dependencies injected: EmotionStore.
"""

from engines.emotion.emotion_state import EmotionState, derive_label
from engines.emotion.emotion_store import EmotionStore


class EmotionUpdater:
    """Service that updates stored emotion states."""

    def __init__(self, emotion_store: EmotionStore, decay_rate: int = 2) -> None:
        """Initialise the updater with a backing store and decay configuration.

        Args:
            emotion_store: Store used to read and persist NPC emotion states.
            decay_rate: Absolute units per tick that valence and arousal decay toward neutral.
        """
        self._store = emotion_store
        self._decay_rate = decay_rate

    def apply_dialogue_mood(self, npc_id: str, mood_update: str | None) -> EmotionState:
        """Apply an optional mood label hint from dialogue output and persist the result.

        If mood_update is None, the current state is decayed toward neutral.
        Otherwise arousal is incremented by 5 (capped at 100) and the label is replaced.

        Args:
            npc_id: Unique identifier of the NPC.
            mood_update: New mood label string, or None to apply passive decay.

        Returns:
            The newly computed and stored EmotionState.
        """
        previous = self._store.get(npc_id=npc_id)
        if mood_update is None:
            next_state = self._decay(previous)
        else:
            next_state = EmotionState(
                valence=previous.valence,
                arousal=min(100, previous.arousal + 5),
                label=mood_update,
            )
        self._store.set(npc_id=npc_id, state=next_state)
        return next_state

    def get_state(self, npc_id: str) -> EmotionState:
        """Return the current emotion state for an NPC.

        Args:
            npc_id: Unique identifier of the NPC.

        Returns:
            Stored EmotionState, or a neutral default if none has been set.
        """
        return self._store.get(npc_id=npc_id)

    def _decay(self, state: EmotionState) -> EmotionState:
        valence = state.valence
        if valence > 0:
            valence = max(0, valence - self._decay_rate)
        elif valence < 0:
            valence = min(0, valence + self._decay_rate)
        arousal = max(0, state.arousal - self._decay_rate)
        return EmotionState(valence=valence, arousal=arousal, label=derive_label(valence, arousal))
