"""
Module: emotion_updater
Layer: engines
Purpose: Applies mood updates and decay rules to emotion states via async store calls.
Does NOT: read or write graph data directly.  Delegates computation to EmotionModelProtocol
          and graph write-through to an injected EmotionGraphPort (no session held).
Dependencies: engines/emotion/emotion_store, engines/emotion/emotion_model_protocol,
              engines/emotion/vad_emotion_model, engines/ports/emotion_port
Dependencies injected: EmotionStore, EmotionModelProtocol, EmotionGraphPort (optional).
Used by: engines/dialogue/dialogue_handler, engines/gossip/gossip_handler
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from npc_engine.engines.emotion.emotion_model_protocol import EmotionModelProtocol
from npc_engine.engines.emotion.emotion_state import EmotionState
from npc_engine.engines.emotion.emotion_store import EmotionStore
from npc_engine.engines.emotion.vad_emotion_model import VadEmotionModel

if TYPE_CHECKING:
    from npc_engine.engines.ports.emotion_port import EmotionGraphPort

_MOOD_AROUSAL_INCREMENT = 5


class EmotionUpdater:
    """Service that updates stored emotion states.

    All emotion computation is delegated to the injected EmotionModelProtocol.
    This class owns only store I/O and method orchestration (OCP / DIP).

    When an EmotionGraphPort is injected, every store write is followed by a
    graph write-through so emotion state survives process restarts.
    """

    def __init__(
        self,
        emotion_store: EmotionStore,
        decay_rate: int = 2,
        model: EmotionModelProtocol | None = None,
        writer: EmotionGraphPort | None = None,
    ) -> None:
        """Initialise the updater with a backing store, decay rate, and optional deps.

        Args:
            emotion_store: Store used to read and persist NPC emotion states.
            decay_rate: Absolute units per tick that valence and arousal decay toward neutral.
            model: EmotionModelProtocol implementation.  Defaults to VadEmotionModel().
            writer: Optional EmotionGraphPort for graph write-through.  When None,
                    state is only stored in-memory (no graph persistence).
        """
        self._store = emotion_store
        self._decay_rate = decay_rate
        self._model: EmotionModelProtocol = model if model is not None else VadEmotionModel()
        self._writer: EmotionGraphPort | None = writer

    async def apply_dialogue_mood(
        self,
        npc_id: str,
        mood_update: str | None,
        tick: int = 0,
    ) -> EmotionState:
        """Apply an optional mood label hint from dialogue output and persist the result.

        If mood_update is None, the current state is decayed toward neutral.
        Otherwise arousal is incremented by 5 (subject to VadEmotionModel label-inertia rules).
        When a writer is injected, the new state is written through to the graph.

        Args:
            npc_id: Unique identifier of the NPC.
            mood_update: New mood label string, or None to apply passive decay.
            tick: Current world-clock tick; stored on the character node.

        Returns:
            The newly computed and stored EmotionState.
        """
        previous = await self._store.get(npc_id=npc_id)
        if mood_update is None:
            next_state = self._model.decay(previous, self._decay_rate)
        else:
            next_state = self._model.apply_mood_hint(
                previous, mood_label=mood_update, arousal_increment=_MOOD_AROUSAL_INCREMENT,
            )
        await self._store.set(npc_id=npc_id, state=next_state)
        await self._write_through(npc_id=npc_id, state=next_state, tick=tick)
        return next_state

    async def get_state(self, npc_id: str) -> EmotionState:
        """Return the current emotion state for an NPC.

        Args:
            npc_id: Unique identifier of the NPC.

        Returns:
            Stored EmotionState, or a neutral default if none has been set.
        """
        return await self._store.get(npc_id=npc_id)

    async def apply_event_shock(
        self,
        npc_id: str,
        severity: int,
        tick: int = 0,
    ) -> EmotionState:
        """Apply an emotional shock when an NPC receives a high-severity rumour or event.

        Decreases valence and increases arousal proportionally to event severity,
        pushing the NPC toward "agitated" or "melancholic".  The effect is bounded
        so a single event cannot force an extreme state.

        When a writer is injected, the new state is also written through to the
        character node in the graph for restart-safe persistence.

        Args:
            npc_id: Unique identifier of the NPC.
            severity: Event severity 0–100; values below 50 produce small shifts.
            tick: Current world-clock tick; stored on the character node.

        Returns:
            The newly computed and stored EmotionState.
        """
        previous = await self._store.get(npc_id=npc_id)
        next_state = self._model.apply_shock(previous, severity)
        await self._store.set(npc_id=npc_id, state=next_state)
        await self._write_through(npc_id=npc_id, state=next_state, tick=tick)
        return next_state

    async def _write_through(
        self,
        *,
        npc_id: str,
        state: EmotionState,
        tick: int,
    ) -> None:
        """Write emotion state through the injected port if one is present."""
        if self._writer is not None:
            await self._writer.write_emotion(
                npc_id=npc_id,
                valence=state.valence,
                arousal=state.arousal,
                label=state.label,
                tick=tick,
            )
