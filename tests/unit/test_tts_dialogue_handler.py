"""Unit tests for TTS integration in DialogueHandler._synthesize_audio."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.dialogue.dialogue_models import DialogueResponse
from npc_engine.engines.emotion.emotion_state import EmotionState
from npc_engine.engines.tts.mock_adapter import MockTTSAdapter
from npc_engine.engines.tts.voice_params import VoiceParams
from npc_engine.utils.errors import TTSSynthesisError


def _make_response(**kwargs) -> DialogueResponse:
    defaults = {
        "npc_response": "Good evening, traveller.",
        "session_id": "player1:mira_innkeeper",
    }
    defaults.update(kwargs)
    return DialogueResponse(**defaults)


# --- _synthesize_audio happy path via mock adapter ---

@pytest.mark.asyncio
async def test_synthesize_audio_attaches_bytes(minimal_handler_with_tts):
    """audio_bytes is populated when the TTS client returns data."""
    handler, tts = minimal_handler_with_tts
    wav = b"RIFF" + b"\x00" * 36
    tts.synthesize = AsyncMock(return_value=wav)

    with patch(
        "npc_engine.engines.dialogue.dialogue_handler.get_npc_voice_descriptor",
        new=AsyncMock(return_value="default"),
    ):
        response = _make_response()
        result = await handler._synthesize_audio(response=response, npc_id="mira_innkeeper")

    assert result.audio_bytes == wav
    assert result.npc_response == response.npc_response


@pytest.mark.asyncio
async def test_synthesize_audio_uses_voice_descriptor_as_voice_id(minimal_handler_with_tts):
    """voice_params.voice_id is derived from the graph voice_descriptor."""
    handler, tts = minimal_handler_with_tts
    tts.synthesize = AsyncMock(return_value=b"")

    with patch(
        "npc_engine.engines.dialogue.dialogue_handler.get_npc_voice_descriptor",
        new=AsyncMock(return_value="Warm, gravelly baritone"),
    ):
        await handler._synthesize_audio(
            response=_make_response(), npc_id="mira_innkeeper"
        )

    call_kwargs = tts.synthesize.call_args
    voice_params: VoiceParams = call_kwargs[1]["voice_params"]
    assert voice_params.voice_id == "Warm, gravelly baritone"


@pytest.mark.asyncio
async def test_synthesize_audio_defaults_voice_id_when_descriptor_is_none(minimal_handler_with_tts):
    handler, tts = minimal_handler_with_tts
    tts.synthesize = AsyncMock(return_value=b"")

    with patch(
        "npc_engine.engines.dialogue.dialogue_handler.get_npc_voice_descriptor",
        new=AsyncMock(return_value=None),
    ):
        await handler._synthesize_audio(
            response=_make_response(), npc_id="unknown_npc"
        )

    voice_params: VoiceParams = tts.synthesize.call_args[1]["voice_params"]
    assert voice_params.voice_id == "default"


@pytest.mark.asyncio
async def test_synthesize_audio_returns_original_on_tts_failure(minimal_handler_with_tts):
    """TTS synthesis errors are silenced; original response returned without audio."""
    handler, tts = minimal_handler_with_tts
    tts.synthesize = AsyncMock(side_effect=TTSSynthesisError(backend="piper", detail="timeout"))

    with patch(
        "npc_engine.engines.dialogue.dialogue_handler.get_npc_voice_descriptor",
        new=AsyncMock(return_value="default"),
    ):
        response = _make_response()
        result = await handler._synthesize_audio(response=response, npc_id="mira_innkeeper")

    assert result.audio_bytes is None
    assert result.npc_response == response.npc_response


# --- Fixtures ---

@pytest.fixture
def minimal_handler_with_tts():
    """Return a DialogueHandler with mocked dependencies and a MockTTSAdapter."""
    from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler
    from npc_engine.engines.dialogue.session_store import SessionStore
    from npc_engine.engines.emotion.emotion_updater import EmotionUpdater
    from npc_engine.services.input_moderation import build_input_moderation_service
    from npc_engine.services.output_moderation import build_output_moderation_service

    mock_settings = MagicMock()
    mock_settings.TTS_ENABLED = True
    mock_settings.LLM_FALLBACK_PATH = "data/fallback_responses.json"
    mock_settings.LOG_LLM_PROMPTS = False
    mock_settings.WORLD_ID = "world_demo"
    mock_settings.CANNED_RESPONSES_DIR = "data/canned_responses"

    mock_llm_config = MagicMock()
    mock_engine_config = MagicMock()
    mock_engine_config.llm.max_tokens = 512
    mock_engine_config.llm.temperature = 0.7
    mock_engine_config.llm.top_p = None
    mock_engine_config.llm.stop_sequences = []

    mock_session = MagicMock()
    mock_session_store = MagicMock(spec=SessionStore)
    mock_emotion_updater = MagicMock(spec=EmotionUpdater)
    mock_emotion_updater.get_state.return_value = EmotionState(valence=0, arousal=0)

    tts = MockTTSAdapter()

    handler = DialogueHandler(
        session=mock_session,
        settings=mock_settings,
        llm_client=MagicMock(),
        llm_config=mock_llm_config,
        engine_model_config=mock_engine_config,
        session_store=mock_session_store,
        emotion_updater=mock_emotion_updater,
        embedding_index=MagicMock(),
        input_moderation=build_input_moderation_service("mature"),
        output_moderation=build_output_moderation_service("mature"),
        tts_client=tts,
    )
    return handler, tts
