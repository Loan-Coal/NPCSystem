"""
Module: voice_modulator
Layer: engines
Purpose: Pure function that maps NPC emotion state to voice parameter adjustments for TTS.
Does NOT: call TTS adapters or perform I/O — modulation is a pure computation.
Dependencies injected: None (pure function; imports from tts/voice_params and emotion/emotion_state).
Used by: dialogue_handler._synthesize_audio
"""

from __future__ import annotations

from npc_engine.engines.emotion.emotion_state import EmotionState
from npc_engine.engines.tts.voice_params import VoiceParams


AROUSAL_HIGH_THRESHOLD: int = 60
VALENCE_POSITIVE_THRESHOLD: int = 40
VALENCE_NEGATIVE_THRESHOLD: int = -40

HIGH_AROUSAL_SPEED_DELTA: float = 0.3
POSITIVE_VALENCE_PITCH_DELTA: float = 2.0
NEGATIVE_VALENCE_PITCH_DELTA: float = -3.0

_SPEED_MIN: float = 0.1
_SPEED_MAX: float = 3.0
_PITCH_MIN: float = -12.0
_PITCH_MAX: float = 12.0


def modulate(base_params: VoiceParams, emotion_state: EmotionState) -> VoiceParams:
    """Return new VoiceParams with speed and pitch adjusted for the NPC's emotion state.

    Mapping rules:
    - arousal >= AROUSAL_HIGH_THRESHOLD: speed += HIGH_AROUSAL_SPEED_DELTA
    - valence <= VALENCE_NEGATIVE_THRESHOLD: pitch_semitones += NEGATIVE_VALENCE_PITCH_DELTA
    - valence >= VALENCE_POSITIVE_THRESHOLD: pitch_semitones += POSITIVE_VALENCE_PITCH_DELTA

    All output values are clamped to VoiceParams field bounds [speed: 0.1–3.0, pitch: -12–12].

    Args:
        base_params: Voice configuration derived from the NPC's voice_descriptor.
        emotion_state: Current NPC emotion with valence [-100, 100] and arousal [0, 100].

    Returns:
        New VoiceParams with emotion-adjusted speed and pitch_semitones.
    """
    speed = base_params.speed
    pitch = base_params.pitch_semitones

    if emotion_state.arousal >= AROUSAL_HIGH_THRESHOLD:
        speed += HIGH_AROUSAL_SPEED_DELTA

    if emotion_state.valence <= VALENCE_NEGATIVE_THRESHOLD:
        pitch += NEGATIVE_VALENCE_PITCH_DELTA
    elif emotion_state.valence >= VALENCE_POSITIVE_THRESHOLD:
        pitch += POSITIVE_VALENCE_PITCH_DELTA

    return VoiceParams(
        voice_id=base_params.voice_id,
        speed=max(_SPEED_MIN, min(_SPEED_MAX, speed)),
        pitch_semitones=max(_PITCH_MIN, min(_PITCH_MAX, pitch)),
    )
