"""
Module: voice_params
Layer: engines
Purpose: Pydantic model carrying per-synthesis voice configuration passed to TTS adapters.
Does NOT: apply emotion modulation (that is S9.2 responsibility).
Dependencies injected: None.
Used by: dialogue_handler, piper_adapter, mock_adapter
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VoiceParams(BaseModel):
    """Immutable voice configuration for a single TTS synthesis call.

    voice_id maps to speaker_id (Piper) or voice_id (ElevenLabs/Azure).
    speed and pitch_semitones are set by S9.2 emotion modulation; S9.1 leaves them at defaults.
    """

    model_config = ConfigDict(frozen=True)

    voice_id: str = "default"
    speed: float = Field(default=1.0, ge=0.1, le=3.0)
    pitch_semitones: float = Field(default=0.0, ge=-12.0, le=12.0)
