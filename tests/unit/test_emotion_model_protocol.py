"""
Module: test_emotion_model_protocol
Layer: tests/unit
Purpose: Unit tests for EmotionModelProtocol and VadEmotionModel.
Dependencies: engines/emotion/emotion_model_protocol, engines/emotion/vad_emotion_model,
              engines/emotion/emotion_updater, engines/emotion/emotion_state,
              engines/emotion/emotion_store
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from npc_engine.engines.emotion.emotion_state import EmotionState
from npc_engine.engines.emotion.emotion_store import EmotionStore
from npc_engine.engines.emotion.emotion_model_protocol import EmotionModelProtocol
from npc_engine.engines.emotion.vad_emotion_model import VadEmotionModel
from npc_engine.engines.emotion.emotion_updater import EmotionUpdater


# ---------------------------------------------------------------------------
# VadEmotionModel — apply_shock
# ---------------------------------------------------------------------------

def test_vad_apply_shock_decreases_valence() -> None:
    """Shock with severity 60 must push valence below zero from neutral."""
    model = VadEmotionModel()
    result = model.apply_shock(EmotionState(), severity=60)
    assert result.valence < 0


def test_vad_apply_shock_increases_arousal() -> None:
    """Shock with severity 60 must raise arousal above zero from neutral."""
    model = VadEmotionModel()
    result = model.apply_shock(EmotionState(), severity=60)
    assert result.arousal > 0


def test_vad_apply_shock_bounded() -> None:
    """Shock cannot push valence below -100 even from a very negative start."""
    model = VadEmotionModel()
    low_valence_state = EmotionState(valence=-90, arousal=0)
    result = model.apply_shock(low_valence_state, severity=100)
    assert result.valence >= -100


# ---------------------------------------------------------------------------
# VadEmotionModel — decay
# ---------------------------------------------------------------------------

def test_vad_decay_moves_toward_neutral() -> None:
    """Positive valence and non-zero arousal must both decrease after decay."""
    model = VadEmotionModel()
    state = EmotionState(valence=20, arousal=30)
    result = model.decay(state, decay_rate=2)
    assert result.valence < 20
    assert result.arousal < 30


def test_vad_decay_does_not_overshoot() -> None:
    """Valence must not cross zero in a single decay step."""
    model = VadEmotionModel()
    state = EmotionState(valence=1, arousal=0)
    result = model.decay(state, decay_rate=5)
    assert result.valence >= 0


# ---------------------------------------------------------------------------
# VadEmotionModel — apply_mood_hint
# ---------------------------------------------------------------------------

def test_vad_apply_mood_hint_replaces_label() -> None:
    """apply_mood_hint must update the state label to the supplied mood."""
    model = VadEmotionModel()
    state = EmotionState(valence=0, arousal=0, label="neutral")
    result = model.apply_mood_hint(state, mood_label="elated", arousal_increment=5)
    assert result.label == "elated"


def test_vad_apply_mood_hint_increments_arousal() -> None:
    """arousal_increment must be added and capped at 100."""
    model = VadEmotionModel()
    state = EmotionState(valence=0, arousal=98)
    result = model.apply_mood_hint(state, mood_label="warm", arousal_increment=5)
    assert result.arousal == 100


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

def test_vad_protocol_conformance() -> None:
    """`isinstance` check must pass for runtime_checkable EmotionModelProtocol."""
    assert isinstance(VadEmotionModel(), EmotionModelProtocol)


# ---------------------------------------------------------------------------
# EmotionUpdater delegates to protocol
# ---------------------------------------------------------------------------

async def test_emotion_updater_uses_protocol_method() -> None:
    """EmotionUpdater.apply_event_shock must delegate to model.apply_shock."""
    store = EmotionStore()
    mock_model = MagicMock(spec=EmotionModelProtocol)
    mock_model.apply_shock.return_value = EmotionState(valence=-10, arousal=20)

    updater = EmotionUpdater(emotion_store=store, model=mock_model)

    await updater.apply_event_shock(npc_id="npc_test", severity=60)

    mock_model.apply_shock.assert_called_once()


# ---------------------------------------------------------------------------
# Behavior parity — outputs identical to pre-refactor expectations
# ---------------------------------------------------------------------------

async def test_behavior_parity_shock() -> None:
    """Output of EmotionUpdater with VadEmotionModel must match pre-refactor math for severity=60."""
    # Pre-refactor constants: VALENCE_DIVISOR=3, VALENCE_CAP=30, AROUSAL_DIVISOR=2, AROUSAL_CAP=40
    # severity=60 → valence_delta=min(30, 60//3)=20; arousal_delta=min(40, 60//2)=30
    # neutral start: valence=0-20=-20; arousal=0+30=30
    store = EmotionStore()
    updater = EmotionUpdater(emotion_store=store, model=VadEmotionModel())

    result = await updater.apply_event_shock(npc_id="npc_test", severity=60)

    assert result.valence == -20
    assert result.arousal == 30
