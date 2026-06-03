"""Unit tests for PiperAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from npc_engine.engines.tts.piper_adapter import PiperAdapter, _build_query_params, _resolve_speaker_id
from npc_engine.engines.tts.protocols import TTSClientProtocol
from npc_engine.engines.tts.voice_params import VoiceParams
from npc_engine.utils.errors import TTSSynthesisError


# --- _resolve_speaker_id ---

def test_resolve_speaker_id_integer_string():
    assert _resolve_speaker_id("3") == 3


def test_resolve_speaker_id_zero():
    assert _resolve_speaker_id("0") == 0


def test_resolve_speaker_id_non_integer_returns_none():
    assert _resolve_speaker_id("default") is None
    assert _resolve_speaker_id("mira_innkeeper") is None
    assert _resolve_speaker_id("") is None


# --- _build_query_params ---

def test_build_query_params_no_speaker_for_default_voice():
    params = _build_query_params("hello", VoiceParams(voice_id="default"))
    assert params["text"] == "hello"
    assert "speaker_id" not in params


def test_build_query_params_adds_speaker_id_when_int():
    params = _build_query_params("hello", VoiceParams(voice_id="2"))
    assert params["text"] == "hello"
    assert params["speaker_id"] == "2"


# --- PiperAdapter.synthesize ---

@pytest.mark.asyncio
async def test_synthesize_returns_content_on_success():
    wav_bytes = b"RIFF" + b"\x00" * 36
    mock_response = MagicMock()
    mock_response.content = wav_bytes
    mock_response.raise_for_status = MagicMock()

    with patch("npc_engine.engines.tts.piper_adapter.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        adapter = PiperAdapter(base_url="http://localhost:5000")
        result = await adapter.synthesize("Hello", VoiceParams())

    assert result == wav_bytes


@pytest.mark.asyncio
async def test_synthesize_raises_on_timeout():
    with patch("npc_engine.engines.tts.piper_adapter.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client_cls.return_value = mock_client

        adapter = PiperAdapter(base_url="http://localhost:5000", timeout_seconds=1.0)
        with pytest.raises(TTSSynthesisError) as exc_info:
            await adapter.synthesize("Hello", VoiceParams())

    assert exc_info.value.backend == "piper"
    assert "timeout" in exc_info.value.detail


@pytest.mark.asyncio
async def test_synthesize_raises_on_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 503

    with patch("npc_engine.engines.tts.piper_adapter.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "503", request=MagicMock(), response=mock_response
            )
        )
        mock_client_cls.return_value = mock_client

        adapter = PiperAdapter(base_url="http://localhost:5000")
        with pytest.raises(TTSSynthesisError) as exc_info:
            await adapter.synthesize("Hello", VoiceParams())

    assert "503" in exc_info.value.detail


# --- PiperAdapter.health_check ---

@pytest.mark.asyncio
async def test_health_check_returns_true_on_success():
    mock_response = MagicMock()
    mock_response.is_success = True

    with patch("npc_engine.engines.tts.piper_adapter.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        adapter = PiperAdapter(base_url="http://localhost:5000")
        result = await adapter.health_check()

    assert result is True


@pytest.mark.asyncio
async def test_health_check_returns_false_on_network_error():
    with patch("npc_engine.engines.tts.piper_adapter.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client_cls.return_value = mock_client

        adapter = PiperAdapter(base_url="http://localhost:5000")
        result = await adapter.health_check()

    assert result is False


def test_piper_backend_name():
    adapter = PiperAdapter(base_url="http://localhost:5000")
    assert adapter.backend_name() == "piper"


def test_piper_satisfies_protocol():
    assert isinstance(PiperAdapter(base_url="http://localhost:5000"), TTSClientProtocol)
