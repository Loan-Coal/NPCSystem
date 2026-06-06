"""
Module: vad_emotion_model
Layer: engines
Purpose: Concrete VAD (Valence-Arousal-Dominance) implementation of EmotionModelProtocol.
         Ports the shock/decay/mood-hint computations formerly embedded in EmotionUpdater.
Dependencies: engines/emotion/emotion_model_protocol, engines/emotion/emotion_state
Used by: engines/emotion/emotion_updater (default injection)
"""
from __future__ import annotations

from npc_engine.engines.emotion.emotion_model_protocol import EmotionModelProtocol
from npc_engine.engines.emotion.emotion_state import EmotionState, derive_label

_SHOCK_VALENCE_DIVISOR = 3
_SHOCK_VALENCE_CAP = 30
_SHOCK_AROUSAL_DIVISOR = 2
_SHOCK_AROUSAL_CAP = 40

_MOOD_AROUSAL_INCREMENT = 5
_AROUSAL_MAX = 100
_AROUSAL_MIN = 0


class VadEmotionModel:
    """VAD emotion model: shock, mood-hint, and decay via valence/arousal arithmetic.

    All methods are pure — no I/O, no mutable state.  Safe to share across
    multiple EmotionUpdater instances.
    """

    def apply_shock(self, state: EmotionState, severity: int) -> EmotionState:
        """Decrease valence and raise arousal proportionally to event severity.

        Args:
            state: Current emotion state before the shock.
            severity: Event severity 0–100.

        Returns:
            New EmotionState with valence decreased and arousal increased,
            both clamped to their valid ranges.
        """
        valence_delta = min(_SHOCK_VALENCE_CAP, severity // _SHOCK_VALENCE_DIVISOR)
        arousal_delta = min(_SHOCK_AROUSAL_CAP, severity // _SHOCK_AROUSAL_DIVISOR)
        new_valence = max(-100, state.valence - valence_delta)
        new_arousal = min(_AROUSAL_MAX, state.arousal + arousal_delta)
        return EmotionState(
            valence=new_valence,
            arousal=new_arousal,
            label=derive_label(new_valence, new_arousal),
        )

    def apply_mood_hint(
        self,
        state: EmotionState,
        mood_label: str,
        arousal_increment: int,
    ) -> EmotionState:
        """Replace label and increment arousal by arousal_increment, capped at 100.

        Args:
            state: Current emotion state.
            mood_label: New label from LLM dialogue output.
            arousal_increment: Amount to add to arousal.

        Returns:
            New EmotionState with updated label and clamped arousal.
        """
        return EmotionState(
            valence=state.valence,
            arousal=min(_AROUSAL_MAX, state.arousal + arousal_increment),
            label=mood_label,
        )

    def decay(self, state: EmotionState, decay_rate: int) -> EmotionState:
        """Move valence and arousal toward neutral by decay_rate without overshooting.

        Args:
            state: Current emotion state.
            decay_rate: Absolute units per tick.

        Returns:
            New EmotionState with valence and arousal closer to zero.
        """
        valence = state.valence
        if valence > 0:
            valence = max(0, valence - decay_rate)
        elif valence < 0:
            valence = min(0, valence + decay_rate)
        arousal = max(_AROUSAL_MIN, state.arousal - decay_rate)
        return EmotionState(
            valence=valence,
            arousal=arousal,
            label=derive_label(valence, arousal),
        )


# Confirm VadEmotionModel satisfies the protocol at import time.
assert isinstance(VadEmotionModel(), EmotionModelProtocol)
