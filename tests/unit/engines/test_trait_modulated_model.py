"""
Tests for TraitModulatedEmotionModel (EXP-219).

Verifies:
  - A high-fear-trait NPC gets a larger negative valence delta than baseline.
  - Neutral traits (all 1.0) produce an output matching VadEmotionModel (LSP parity).
  - apply_mood_hint and decay pass-through correctly with neutral traits.
"""
from __future__ import annotations

import pytest

from npc_engine.engines.emotion.emotion_state import EmotionState
from npc_engine.engines.emotion.vad_emotion_model import VadEmotionModel
from npc_engine.engines.emotion.trait_modulated_model import TraitModulatedEmotionModel


_NEUTRAL_TRAITS: dict[str, float] = {
    "fear_sensitivity": 1.0,
    "anger_sensitivity": 1.0,
    "joy_sensitivity": 1.0,
}

_HIGH_FEAR_TRAITS: dict[str, float] = {
    "fear_sensitivity": 2.0,
    "anger_sensitivity": 1.0,
    "joy_sensitivity": 1.0,
}


@pytest.fixture()
def baseline_state() -> EmotionState:
    return EmotionState(valence=0, arousal=0, label="neutral")


class TestHighFearTraitAmplifiesFearDelta:
    """A high-fear-trait NPC suffers a larger valence drop on shock than baseline."""

    def test_high_fear_trait_amplifies_valence_drop(
        self, baseline_state: EmotionState
    ) -> None:
        base_model = VadEmotionModel()
        trait_model = TraitModulatedEmotionModel(traits=_HIGH_FEAR_TRAITS)

        base_result = base_model.apply_shock(baseline_state, severity=60)
        trait_result = trait_model.apply_shock(baseline_state, severity=60)

        # Higher fear sensitivity → more negative valence (larger drop from 0)
        assert trait_result.valence < base_result.valence

    def test_high_fear_trait_amplifies_arousal_increase(
        self, baseline_state: EmotionState
    ) -> None:
        base_model = VadEmotionModel()
        trait_model = TraitModulatedEmotionModel(traits=_HIGH_FEAR_TRAITS)

        base_result = base_model.apply_shock(baseline_state, severity=60)
        trait_result = trait_model.apply_shock(baseline_state, severity=60)

        assert trait_result.arousal >= base_result.arousal


class TestNeutralTraitsMatchBaseModel:
    """Neutral traits (all 1.0) reproduce VadEmotionModel results exactly (LSP parity)."""

    def test_apply_shock_matches_base(self, baseline_state: EmotionState) -> None:
        base_model = VadEmotionModel()
        trait_model = TraitModulatedEmotionModel(traits=_NEUTRAL_TRAITS)

        base_result = base_model.apply_shock(baseline_state, severity=60)
        trait_result = trait_model.apply_shock(baseline_state, severity=60)

        assert trait_result.valence == base_result.valence
        assert trait_result.arousal == base_result.arousal

    def test_apply_mood_hint_matches_base(self, baseline_state: EmotionState) -> None:
        base_model = VadEmotionModel()
        trait_model = TraitModulatedEmotionModel(traits=_NEUTRAL_TRAITS)

        base_result = base_model.apply_mood_hint(
            baseline_state, mood_label="agitated", arousal_increment=30
        )
        trait_result = trait_model.apply_mood_hint(
            baseline_state, mood_label="agitated", arousal_increment=30
        )

        assert trait_result.valence == base_result.valence
        assert trait_result.arousal == base_result.arousal
        assert trait_result.label == base_result.label

    def test_decay_matches_base(self) -> None:
        state = EmotionState(valence=-50, arousal=80, label="agitated")
        base_model = VadEmotionModel()
        trait_model = TraitModulatedEmotionModel(traits=_NEUTRAL_TRAITS)

        base_result = base_model.decay(state, decay_rate=10)
        trait_result = trait_model.decay(state, decay_rate=10)

        assert trait_result.valence == base_result.valence
        assert trait_result.arousal == base_result.arousal


class TestProtocolConformance:
    """TraitModulatedEmotionModel satisfies EmotionModelProtocol at runtime."""

    def test_isinstance_protocol(self) -> None:
        from npc_engine.engines.emotion.emotion_model_protocol import EmotionModelProtocol

        model = TraitModulatedEmotionModel(traits=_NEUTRAL_TRAITS)
        assert isinstance(model, EmotionModelProtocol)
