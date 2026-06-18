"""Unit tests for MockTTSAdapter."""

from __future__ import annotations

import pytest

from npc_engine.engines.tts.mock_adapter import MockTTSAdapter
from npc_engine.engines.tts.protocols import TTSClientProtocol
from npc_engine.engines.tts.voice_params import VoiceParams


@pytest.mark.asyncio
async def test_mock_synthesize_returns_empty_bytes():
    adapter = MockTTSAdapter()
    result = await adapter.synthesize("Hello there", VoiceParams())
    assert result == b""


@pytest.mark.asyncio
async def test_mock_synthesize_any_voice_params():
    adapter = MockTTSAdapter()
    result = await adapter.synthesize("x", VoiceParams(voice_id="7", speed=2.0))
    assert isinstance(result, bytes)


@pytest.mark.asyncio
async def test_mock_health_check_returns_true():
    adapter = MockTTSAdapter()
    assert await adapter.health_check() is True


def test_mock_backend_name():
    assert MockTTSAdapter().backend_name() == "mock"


def test_mock_satisfies_protocol():
    assert isinstance(MockTTSAdapter(), TTSClientProtocol)
