"""Unit tests for voice_modulator.modulate()."""

from __future__ import annotations

import pytest

from npc_engine.engines.emotion.emotion_state import EmotionState
from npc_engine.engines.tts.voice_modulator import (
    AROUSAL_HIGH_THRESHOLD,
    HIGH_AROUSAL_SPEED_DELTA,
    NEGATIVE_VALENCE_PITCH_DELTA,
    POSITIVE_VALENCE_PITCH_DELTA,
    VALENCE_NEGATIVE_THRESHOLD,
    VALENCE_POSITIVE_THRESHOLD,
    modulate,
)
from npc_engine.engines.tts.voice_params import VoiceParams


def _emotion(valence: int = 0, arousal: int = 0) -> EmotionState:
    return EmotionState(valence=valence, arousal=arousal)


def _base(speed: float = 1.0, pitch: float = 0.0, voice_id: str = "default") -> VoiceParams:
    return VoiceParams(voice_id=voice_id, speed=speed, pitch_semitones=pitch)


def test_neutral_emotion_leaves_params_unchanged():
    result = modulate(_base(), _emotion(valence=0, arousal=0))
    assert result.speed == pytest.approx(1.0)
    assert result.pitch_semitones == pytest.approx(0.0)


def test_high_arousal_increases_speed():
    result = modulate(_base(), _emotion(arousal=AROUSAL_HIGH_THRESHOLD))
    assert result.speed == pytest.approx(1.0 + HIGH_AROUSAL_SPEED_DELTA)


def test_below_arousal_threshold_does_not_change_speed():
    result = modulate(_base(), _emotion(arousal=AROUSAL_HIGH_THRESHOLD - 1))
    assert result.speed == pytest.approx(1.0)


def test_negative_valence_lowers_pitch():
    result = modulate(_base(), _emotion(valence=VALENCE_NEGATIVE_THRESHOLD))
    assert result.pitch_semitones == pytest.approx(NEGATIVE_VALENCE_PITCH_DELTA)


def test_positive_valence_raises_pitch():
    result = modulate(_base(), _emotion(valence=VALENCE_POSITIVE_THRESHOLD))
    assert result.pitch_semitones == pytest.approx(POSITIVE_VALENCE_PITCH_DELTA)


def test_mid_valence_does_not_change_pitch():
    result = modulate(_base(), _emotion(valence=10))
    assert result.pitch_semitones == pytest.approx(0.0)


def test_high_arousal_and_negative_valence_stack():
    result = modulate(
        _base(),
        _emotion(valence=VALENCE_NEGATIVE_THRESHOLD, arousal=AROUSAL_HIGH_THRESHOLD),
    )
    assert result.speed == pytest.approx(1.0 + HIGH_AROUSAL_SPEED_DELTA)
    assert result.pitch_semitones == pytest.approx(NEGATIVE_VALENCE_PITCH_DELTA)


def test_voice_id_preserved():
    result = modulate(_base(voice_id="gravelly_baritone"), _emotion())
    assert result.voice_id == "gravelly_baritone"


def test_speed_clamped_to_max():
    result = modulate(_base(speed=3.0), _emotion(arousal=AROUSAL_HIGH_THRESHOLD))
    assert result.speed <= 3.0


def test_pitch_not_below_min():
    result = modulate(_base(pitch=-11.0), _emotion(valence=VALENCE_NEGATIVE_THRESHOLD))
    assert result.pitch_semitones >= -12.0


def test_extreme_negative_valence_clamps_pitch():
    result = modulate(_base(pitch=-10.0), _emotion(valence=-100))
    assert result.pitch_semitones == pytest.approx(-12.0)


def test_exit_criterion_different_params_for_extreme_valences():
    """Same base params, valence < -40 vs valence > 40 → measurably different VoiceParams."""
    base = _base()
    negative = modulate(base, _emotion(valence=-50))
    positive = modulate(base, _emotion(valence=50))
    assert negative.pitch_semitones < positive.pitch_semitones
