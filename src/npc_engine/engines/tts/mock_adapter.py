"""
Module: mock_adapter
Layer: engines
Purpose: Silent TTS adapter for unit tests and TTS_ENABLED=false dry-run paths.
Does NOT: make network calls; always returns empty bytes.
Dependencies injected: None.
Used by: tests, api/dependencies when TTS_BACKEND="mock"
"""

from __future__ import annotations

from npc_engine.engines.tts.voice_params import VoiceParams

_BACKEND_NAME = "mock"


class MockTTSAdapter:
    """No-op TTS adapter that returns empty bytes without making network calls.

    Matches TTSClientProtocol. Used in unit tests and when TTS_BACKEND=mock.
    """

    async def synthesize(self, text: str, voice_params: VoiceParams) -> bytes:
        """Return empty bytes without calling any backend.

        Args:
            text: Ignored.
            voice_params: Ignored.

        Returns:
            Empty bytes (b"").
        """
        return b""

    async def health_check(self) -> bool:
        """Always return True. No network calls.

        Returns:
            True.
        """
        return True

    def backend_name(self) -> str:
        """Return 'mock'."""
        return _BACKEND_NAME
