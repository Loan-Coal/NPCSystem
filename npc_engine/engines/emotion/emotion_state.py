"""
emotion_state.py - Emotion state model and label derivation helpers.

Does NOT: persist emotion state by itself.

Dependencies injected: None.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class EmotionState(BaseModel):
    """Persistent emotion state for an NPC."""

    valence: int = Field(default=0, ge=-100, le=100)
    arousal: int = Field(default=0, ge=0, le=100)
    label: str = "neutral"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


def derive_label(valence: int, arousal: int) -> str:
    """Derive coarse mood label from valence/arousal coordinates."""

    if arousal >= 70 and valence < -20:
        return "agitated"
    if arousal >= 70 and valence >= 20:
        return "elated"
    if valence <= -30:
        return "melancholic"
    if valence >= 30:
        return "warm"
    return "neutral"
