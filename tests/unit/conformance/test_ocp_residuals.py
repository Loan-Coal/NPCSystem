"""
test_ocp_residuals.py — Unit tests for REM-W4 OCP residuals (ISSUE-104).

Verifies that the four OCP-residual fixes are in place:
1. emotion_model_factory has a registry (registered_emotion_models).
2. emotion_state exports MOOD_LABEL_TO_VAD (single shared table).
3. covert_event_factory defines SchemeStepKind enum.
4. engines/tts/factory has a registry (registered_tts_backends + build_tts_client).
"""

from __future__ import annotations

from enum import Enum
from types import SimpleNamespace


# ---------------------------------------------------------------------------
# 1. Emotion model registry
# ---------------------------------------------------------------------------


def test_registered_emotion_models_returns_builtins() -> None:
    """registered_emotion_models() exposes at least vad and trait_modulated."""
    from npc_engine.engines.emotion.emotion_model_factory import registered_emotion_models

    backends = registered_emotion_models()
    assert "vad" in backends
    assert "trait_modulated" in backends


def test_register_emotion_model_extends_registry() -> None:
    """register_emotion_model adds a new entry without mutating existing ones."""
    from npc_engine.engines.emotion.emotion_model_factory import (
        _EMOTION_REGISTRY,
        register_emotion_model,
        registered_emotion_models,
    )
    from npc_engine.engines.emotion.vad_emotion_model import VadEmotionModel

    before = set(registered_emotion_models())
    register_emotion_model("_test_ocp_stub", VadEmotionModel)
    try:
        assert "_test_ocp_stub" in registered_emotion_models()
        # Original entries survive
        assert "vad" in registered_emotion_models()
    finally:
        _EMOTION_REGISTRY.pop("_test_ocp_stub", None)


def test_build_emotion_model_dispatches_via_registry() -> None:
    """build_emotion_model returns the registered implementation for the name."""
    from npc_engine.engines.emotion.emotion_model_factory import build_emotion_model
    from npc_engine.engines.emotion.vad_emotion_model import VadEmotionModel
    from npc_engine.engines.emotion.trait_modulated_model import TraitModulatedEmotionModel

    settings_vad = SimpleNamespace(EMOTION_MODEL="vad")
    settings_trait = SimpleNamespace(EMOTION_MODEL="trait_modulated")

    assert isinstance(build_emotion_model(settings_vad), VadEmotionModel)
    assert isinstance(build_emotion_model(settings_trait), TraitModulatedEmotionModel)


# ---------------------------------------------------------------------------
# 2. Shared mood→VAD table in emotion_state
# ---------------------------------------------------------------------------


def test_mood_label_to_vad_exported_from_emotion_state() -> None:
    """MOOD_LABEL_TO_VAD is accessible from emotion_state."""
    from npc_engine.engines.emotion.emotion_state import MOOD_LABEL_TO_VAD

    assert isinstance(MOOD_LABEL_TO_VAD, dict)


def test_mood_label_to_vad_covers_all_labels() -> None:
    """MOOD_LABEL_TO_VAD has entries for all five canonical mood labels."""
    from npc_engine.engines.emotion.emotion_state import MOOD_LABEL_TO_VAD

    expected = {"elated", "warm", "neutral", "melancholic", "agitated"}
    assert set(MOOD_LABEL_TO_VAD.keys()) == expected


def test_mood_label_to_vad_values_are_int_tuples() -> None:
    """Each MOOD_LABEL_TO_VAD value is a (valence: int, arousal: int) tuple."""
    from npc_engine.engines.emotion.emotion_state import MOOD_LABEL_TO_VAD

    for label, pair in MOOD_LABEL_TO_VAD.items():
        assert isinstance(pair, tuple) and len(pair) == 2, f"{label}: expected 2-tuple"
        v, a = pair
        assert isinstance(v, int), f"{label}: valence must be int"
        assert isinstance(a, int), f"{label}: arousal must be int"


def test_mood_contagion_uses_shared_table() -> None:
    """MoodContagionEngine does not define its own _LABEL_TO_VALENCE_AROUSAL."""
    import npc_engine.engines.mood.mood_contagion_engine as mod

    assert not hasattr(mod, "_LABEL_TO_VALENCE_AROUSAL"), (
        "Local _LABEL_TO_VALENCE_AROUSAL should be removed; "
        "use MOOD_LABEL_TO_VAD from emotion_state"
    )


# ---------------------------------------------------------------------------
# 3. SchemeStepKind enum
# ---------------------------------------------------------------------------


def test_scheme_step_kind_is_enum() -> None:
    """SchemeStepKind is an Enum with at least an ADVANCE member."""
    from npc_engine.engines.scheming.covert_event_factory import SchemeStepKind

    assert issubclass(SchemeStepKind, Enum)
    assert hasattr(SchemeStepKind, "ADVANCE")


def test_scheme_step_kind_advance_equals_constant() -> None:
    """SchemeStepKind.ADVANCE equals 'scheme_advance' and the existing constant."""
    from npc_engine.engines.scheming.covert_event_factory import (
        COVERT_SCHEME_EVENT_TYPE,
        SchemeStepKind,
    )

    assert SchemeStepKind.ADVANCE == "scheme_advance"
    assert SchemeStepKind.ADVANCE == COVERT_SCHEME_EVENT_TYPE


# ---------------------------------------------------------------------------
# 4. TTS backend registry
# ---------------------------------------------------------------------------


def test_registered_tts_backends_returns_builtins() -> None:
    """registered_tts_backends() exposes at least piper and mock."""
    from npc_engine.engines.tts.factory import registered_tts_backends

    backends = registered_tts_backends()
    assert "piper" in backends
    assert "mock" in backends


def test_register_tts_backend_extends_registry() -> None:
    """register_tts_backend adds a new entry without mutating existing ones."""
    from npc_engine.engines.tts.factory import (
        _TTS_REGISTRY,
        register_tts_backend,
        registered_tts_backends,
    )
    from npc_engine.engines.tts.mock_adapter import MockTTSAdapter

    register_tts_backend("_test_tts_stub", lambda s: MockTTSAdapter())
    try:
        assert "_test_tts_stub" in registered_tts_backends()
        assert "piper" in registered_tts_backends()
    finally:
        _TTS_REGISTRY.pop("_test_tts_stub", None)


def test_build_tts_client_returns_none_when_disabled() -> None:
    """build_tts_client returns None when TTS_ENABLED is False."""
    from npc_engine.engines.tts.factory import build_tts_client

    settings = SimpleNamespace(TTS_ENABLED=False, TTS_BACKEND="piper")
    result = build_tts_client(settings)
    assert result is None


def test_build_tts_client_returns_mock_when_enabled() -> None:
    """build_tts_client returns a MockTTSAdapter for TTS_BACKEND='mock'."""
    from npc_engine.engines.tts.factory import build_tts_client
    from npc_engine.engines.tts.mock_adapter import MockTTSAdapter

    settings = SimpleNamespace(TTS_ENABLED=True, TTS_BACKEND="mock")
    result = build_tts_client(settings)
    assert isinstance(result, MockTTSAdapter)


def test_build_tts_client_raises_for_unknown_backend() -> None:
    """build_tts_client raises ValueError for an unregistered backend name."""
    from npc_engine.engines.tts.factory import build_tts_client

    settings = SimpleNamespace(TTS_ENABLED=True, TTS_BACKEND="nonexistent_backend_xyz")
    try:
        build_tts_client(settings)
        raise AssertionError("Expected ValueError")
    except ValueError as exc:
        assert "nonexistent_backend_xyz" in str(exc)
