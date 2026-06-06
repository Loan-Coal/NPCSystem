"""
Module: emotion_model_protocol
Layer: engines
Purpose: Runtime-checkable Protocol defining the emotion computation contract.
Dependencies: engines/emotion/emotion_state
Used by: engines/emotion/emotion_updater, engines/emotion/vad_emotion_model
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from npc_engine.engines.emotion.emotion_state import EmotionState


@runtime_checkable
class EmotionModelProtocol(Protocol):
    """Compute pure emotion state transitions given events and decay.

    Implementations are pure functions of their inputs — no I/O, no store
    access.  All side-effects (store reads/writes) remain in EmotionUpdater.
    """

    def apply_shock(self, state: EmotionState, severity: int) -> EmotionState:
        """Apply emotional shock from a high-severity event.

        Args:
            state: Current emotion state before the shock.
            severity: Event severity 0–100; values below 50 produce small shifts.

        Returns:
            A new EmotionState with valence decreased and arousal increased
            proportionally to severity, bounded to [-100, 100].
        """
        ...

    def apply_mood_hint(
        self,
        state: EmotionState,
        mood_label: str,
        arousal_increment: int,
    ) -> EmotionState:
        """Apply a mood label hint from dialogue output to the existing state.

        Args:
            state: Current emotion state.
            mood_label: New mood label string from LLM dialogue output.
            arousal_increment: Amount to add to arousal (capped at 100).

        Returns:
            A new EmotionState with updated label and incremented arousal.
        """
        ...

    def decay(self, state: EmotionState, decay_rate: int) -> EmotionState:
        """Apply passive decay toward neutral.

        Args:
            state: Current emotion state.
            decay_rate: Absolute units per tick that valence and arousal
                approach zero.

        Returns:
            A new EmotionState with valence and arousal moved toward neutral
            without overshooting zero.
        """
        ...
