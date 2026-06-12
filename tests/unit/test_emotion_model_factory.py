"""
test_emotion_model_factory.py - Unit tests for build_emotion_model selector.

Verifies config-selectable emotion model construction (F1.3): "vad" yields the
baseline VadEmotionModel; "trait_modulated" yields a TraitModulatedEmotionModel
whose default demo traits visibly amplify a shock relative to the baseline.

Dependencies injected: SimpleNamespace settings stub (only EMOTION_MODEL is read).
"""

from __future__ import annotations

from types import SimpleNamespace

from npc_engine.engines.emotion.emotion_model_factory import build_emotion_model
from npc_engine.engines.emotion.emotion_state import EmotionState
from npc_engine.engines.emotion.trait_modulated_model import TraitModulatedEmotionModel
from npc_engine.engines.emotion.vad_emotion_model import VadEmotionModel


def _settings(model: str) -> SimpleNamespace:
    return SimpleNamespace(EMOTION_MODEL=model)


def test_vad_selection_returns_vad_model() -> None:
    """EMOTION_MODEL='vad' builds the baseline VadEmotionModel."""
    model = build_emotion_model(_settings("vad"))
    assert isinstance(model, VadEmotionModel)


def test_trait_selection_returns_trait_model() -> None:
    """EMOTION_MODEL='trait_modulated' builds a TraitModulatedEmotionModel."""
    model = build_emotion_model(_settings("trait_modulated"))
    assert isinstance(model, TraitModulatedEmotionModel)


def test_trait_model_amplifies_shock_vs_baseline() -> None:
    """The trait model's default demo traits modulate a live shock delta (> baseline)."""
    baseline = build_emotion_model(_settings("vad"))
    trait = build_emotion_model(_settings("trait_modulated"))
    start = EmotionState(valence=0, arousal=0)

    base_after = baseline.apply_shock(start, severity=90)
    trait_after = trait.apply_shock(start, severity=90)

    # Default demo fear_sensitivity > 1.0 → larger negative valence + higher arousal.
    assert trait_after.valence < base_after.valence
    assert trait_after.arousal > base_after.arousal


def test_composition_root_injects_configured_model(monkeypatch) -> None:
    """get_emotion_updater injects the settings-selected model into EmotionUpdater."""
    from npc_engine.api import dependencies_stores as ds

    ds.get_emotion_updater.cache_clear()
    monkeypatch.setattr(ds, "get_settings", lambda: _settings("trait_modulated"))
    try:
        updater = ds.get_emotion_updater()
        assert isinstance(updater._model, TraitModulatedEmotionModel)
    finally:
        ds.get_emotion_updater.cache_clear()
