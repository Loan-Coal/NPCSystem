"""
emotion_updater.py - Applies mood updates and decay rules to emotion states.

Does NOT: read or write graph data.

Dependencies injected: EmotionStore.
"""

from engines.emotion.emotion_state import EmotionState, derive_label
from engines.emotion.emotion_store import EmotionStore


class EmotionUpdater:
    """Service that updates stored emotion states."""

    def __init__(self, emotion_store: EmotionStore, decay_rate: int = 2):
        self._store = emotion_store
        self._decay_rate = decay_rate

    def apply_dialogue_mood(self, npc_id: str, mood_update: str | None) -> EmotionState:
        """Apply optional mood label hint from dialogue output."""

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
        """Return current emotion state for NPC."""

        return self._store.get(npc_id=npc_id)

    def _decay(self, state: EmotionState) -> EmotionState:
        valence = state.valence
        if valence > 0:
            valence = max(0, valence - self._decay_rate)
        elif valence < 0:
            valence = min(0, valence + self._decay_rate)
        arousal = max(0, state.arousal - self._decay_rate)
        return EmotionState(valence=valence, arousal=arousal, label=derive_label(valence, arousal))
