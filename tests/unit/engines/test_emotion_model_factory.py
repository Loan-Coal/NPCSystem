"""
test_emotion_model_factory.py - Unit tests for build_emotion_model selector.

Verifies config-selectable emotion model construction (F1.3): "vad" yields the
baseline VadEmotionModel.

Dependencies injected: SimpleNamespace settings stub (only EMOTION_MODEL is read).
"""

from __future__ import annotations

from types import SimpleNamespace

from npc_engine.engines.emotion.emotion_model_factory import build_emotion_model
from npc_engine.engines.emotion.vad_emotion_model import VadEmotionModel


def _settings(model: str) -> SimpleNamespace:
    return SimpleNamespace(EMOTION_MODEL=model)


def test_vad_selection_returns_vad_model() -> None:
    """EMOTION_MODEL='vad' builds the baseline VadEmotionModel."""
    model = build_emotion_model(_settings("vad"))
    assert isinstance(model, VadEmotionModel)


def test_unknown_model_raises_value_error() -> None:
    """build_emotion_model raises ValueError for an unregistered name."""
    try:
        build_emotion_model(_settings("nonexistent_model_xyz"))
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "nonexistent_model_xyz" in str(exc)
