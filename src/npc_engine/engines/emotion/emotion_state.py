"""
emotion_state.py - Emotion state model and label derivation helpers.
Layer: engines
Purpose: Emotion state model and label derivation helpers.

Does NOT: persist emotion state by itself.

Dependencies injected: None.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


# Canonical mapping from mood label → (valence, arousal) reference coordinates.
# Single source of truth shared by mood_contagion_engine (label→VAD reconstruction)
# and any future module needing the inverse of derive_label.
# Values mirror the thresholds in derive_label: e.g. elated ≥ 70 arousal + ≥ 20 valence.
MOOD_LABEL_TO_VAD: dict[str, tuple[int, int]] = {
    "elated": (60, 80),
    "warm": (50, 40),
    "neutral": (0, 20),
    "melancholic": (-50, 30),
    "agitated": (-60, 80),
}


class EmotionState(BaseModel):
    """Persistent emotion state for an NPC."""

    valence: int = Field(default=0, ge=-100, le=100)
    arousal: int = Field(default=0, ge=0, le=100)
    label: str = "neutral"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


def derive_label(valence: int, arousal: int) -> str:
    """Derive coarse mood label from valence/arousal coordinates.

    Args:
        valence: Pleasure–displeasure axis, clamped to [-100, 100].
        arousal: Activation level, clamped to [0, 100].

    Returns:
        One of "agitated", "elated", "melancholic", "warm", or "neutral".
    """
    if arousal >= 70 and valence < -20:
        return "agitated"
    if arousal >= 70 and valence >= 20:
        return "elated"
    if valence <= -30:
        return "melancholic"
    if valence >= 30:
        return "warm"
    return "neutral"
