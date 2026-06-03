"""
Module: protocols
Layer: engines
Purpose: TTSClientProtocol defining the contract for all TTS backend adapters.
Does NOT: implement any backend; concrete adapters live in piper_adapter, mock_adapter.
Dependencies injected: None.
Used by: dialogue_handler, piper_adapter, mock_adapter, api/dependencies
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from npc_engine.engines.tts.voice_params import VoiceParams


@runtime_checkable
class TTSClientProtocol(Protocol):
    """Contract for all TTS adapter implementations.

    Implementors must be injectable via constructor and must not instantiate
    network clients at module level (DIP strict rule).
    """

    async def synthesize(self, text: str, voice_params: VoiceParams) -> bytes:
        """Synthesize speech from text and return raw audio bytes (WAV or MP3).

        Args:
            text: The NPC utterance to synthesize.
            voice_params: Voice configuration (id, speed, pitch).

        Returns:
            Raw audio bytes (format determined by adapter, typically WAV).

        Raises:
            TTSSynthesisError: If the backend returns an error or times out.
        """

    async def health_check(self) -> bool:
        """Return True if the TTS backend is reachable and ready. Non-raising.

        Returns:
            True if the backend responded successfully, False on any error.
        """

    def backend_name(self) -> str:
        """Return a short identifier for this backend.

        Returns:
            Backend identifier string (e.g. "piper", "mock").
        """
