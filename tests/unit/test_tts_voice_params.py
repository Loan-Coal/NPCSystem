"""Unit tests for VoiceParams model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from npc_engine.engines.tts.voice_params import VoiceParams


def test_voice_params_defaults():
    vp = VoiceParams()
    assert vp.voice_id == "default"
    assert vp.speed == 1.0
    assert vp.pitch_semitones == 0.0


def test_voice_params_custom_values():
    vp = VoiceParams(voice_id="3", speed=1.5, pitch_semitones=-2.0)
    assert vp.voice_id == "3"
    assert vp.speed == 1.5
    assert vp.pitch_semitones == -2.0


def test_voice_params_speed_bounds():
    with pytest.raises(ValidationError):
        VoiceParams(speed=0.0)
    with pytest.raises(ValidationError):
        VoiceParams(speed=3.1)


def test_voice_params_pitch_bounds():
    with pytest.raises(ValidationError):
        VoiceParams(pitch_semitones=-13.0)
    with pytest.raises(ValidationError):
        VoiceParams(pitch_semitones=13.0)


def test_voice_params_is_frozen():
    vp = VoiceParams()
    with pytest.raises(Exception):
        vp.voice_id = "new"  # type: ignore[misc]
