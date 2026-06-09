"""
Module: emotion_updater
Layer: engines
Purpose: Applies mood updates and decay rules to emotion states via async store calls.
Does NOT: read or write graph data. Does NOT compute emotion arithmetic directly —
          delegates all computation to the injected EmotionModelProtocol.
Dependencies: engines/emotion/emotion_store, engines/emotion/emotion_model_protocol,
              engines/emotion/vad_emotion_model
Dependencies injected: EmotionStore, EmotionModelProtocol.
Used by: engines/dialogue/dialogue_handler, engines/gossip/gossip_handler
"""

from __future__ import annotations

from npc_engine.engines.emotion.emotion_model_protocol import EmotionModelProtocol
from npc_engine.engines.emotion.emotion_state import EmotionState
from npc_engine.engines.emotion.emotion_store import EmotionStore
from npc_engine.engines.emotion.vad_emotion_model import VadEmotionModel

_MOOD_AROUSAL_INCREMENT = 5


class EmotionUpdater:
    """Service that updates stored emotion states.

    All emotion computation is delegated to the injected EmotionModelProtocol.
    This class owns only store I/O and method orchestration (OCP / DIP).
    """

    def __init__(
        self,
        emotion_store: EmotionStore,
        decay_rate: int = 2,
        model: EmotionModelProtocol | None = None,
    ) -> None:
        """Initialise the updater with a backing store, decay rate, and optional model.

        Args:
            emotion_store: Store used to read and persist NPC emotion states.
            decay_rate: Absolute units per tick that valence and arousal decay toward neutral.
            model: EmotionModelProtocol implementation.  Defaults to VadEmotionModel().
        """
        self._store = emotion_store
        self._decay_rate = decay_rate
        self._model: EmotionModelProtocol = model if model is not None else VadEmotionModel()

    async def apply_dialogue_mood(self, npc_id: str, mood_update: str | None) -> EmotionState:
        """Apply an optional mood label hint from dialogue output and persist the result.

        If mood_update is None, the current state is decayed toward neutral.
        Otherwise arousal is incremented by 5 (capped at 100) and the label is replaced.

        Args:
            npc_id: Unique identifier of the NPC.
            mood_update: New mood label string, or None to apply passive decay.

        Returns:
            The newly computed and stored EmotionState.
        """
        previous = await self._store.get(npc_id=npc_id)
        if mood_update is None:
            next_state = self._model.decay(previous, self._decay_rate)
        else:
            next_state = self._model.apply_mood_hint(
                previous,
                mood_label=mood_update,
                arousal_increment=_MOOD_AROUSAL_INCREMENT,
            )
        await self._store.set(npc_id=npc_id, state=next_state)
        return next_state

    async def get_state(self, npc_id: str) -> EmotionState:
        """Return the current emotion state for an NPC.

        Args:
            npc_id: Unique identifier of the NPC.

        Returns:
            Stored EmotionState, or a neutral default if none has been set.
        """
        return await self._store.get(npc_id=npc_id)

    async def apply_event_shock(self, npc_id: str, severity: int) -> EmotionState:
        """Apply an emotional shock when an NPC receives a high-severity rumour or event.

        Decreases valence and increases arousal proportionally to event severity,
        pushing the NPC toward "agitated" or "melancholic".  The effect is bounded
        so a single event cannot force an extreme state.

        Args:
            npc_id: Unique identifier of the NPC.
            severity: Event severity 0–100; values below 50 produce small shifts.

        Returns:
            The newly computed and stored EmotionState.
        """
        previous = await self._store.get(npc_id=npc_id)
        next_state = self._model.apply_shock(previous, severity)
        await self._store.set(npc_id=npc_id, state=next_state)
        return next_state
