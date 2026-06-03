"""
Module: piper_adapter
Layer: engines
Purpose: TTS adapter for Piper local HTTP server (no API key required).
Does NOT: implement cloud TTS; for ElevenLabs/Azure add a separate adapter file.
Dependencies injected: base_url, timeout_seconds.
Used by: api/dependencies (composition root)
"""

from __future__ import annotations

from urllib.parse import quote

import httpx

from npc_engine.engines.tts.voice_params import VoiceParams
from npc_engine.utils.errors import TTSSynthesisError

_PIPER_TTS_PATH = "/api/tts"
_PIPER_HEALTH_PATH = "/api/tts"
_PIPER_HEALTH_PROBE = "hello"
_BACKEND_NAME = "piper"


class PiperAdapter:
    """Adapter for a locally-running Piper TTS HTTP server.

    Piper serves WAV audio at GET {base_url}/api/tts?text=<text>.
    Multi-speaker models accept an additional speaker_id parameter derived
    from voice_params.voice_id when it parses as an integer.
    """

    def __init__(self, base_url: str, timeout_seconds: float = 10.0) -> None:
        """Initialise the adapter with Piper endpoint configuration.

        Args:
            base_url: Root URL of the Piper HTTP server (e.g. "http://localhost:5000").
            timeout_seconds: Per-request timeout in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def close(self) -> None:
        """Release the shared HTTP client. Call at application shutdown."""
        await self._client.aclose()

    async def synthesize(self, text: str, voice_params: VoiceParams) -> bytes:
        """Request audio synthesis from Piper and return raw WAV bytes.

        Args:
            text: NPC utterance to synthesize.
            voice_params: Voice configuration; voice_id used as speaker_id when int-parseable.

        Returns:
            WAV audio bytes from Piper.

        Raises:
            TTSSynthesisError: On HTTP error or network timeout.
        """
        params = _build_query_params(text=text, voice_params=voice_params)
        url = f"{self._base_url}{_PIPER_TTS_PATH}"
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            return response.content
        except httpx.TimeoutException as exc:
            raise TTSSynthesisError(
                backend=_BACKEND_NAME, detail=f"timeout after {self._timeout_seconds}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise TTSSynthesisError(
                backend=_BACKEND_NAME, detail=f"HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise TTSSynthesisError(
                backend=_BACKEND_NAME, detail=str(exc)
            ) from exc

    async def health_check(self) -> bool:
        """Return True if the Piper server is reachable. Non-raising.

        Returns:
            True if the backend responded successfully, False on any error.
        """
        try:
            params = _build_query_params(
                text=_PIPER_HEALTH_PROBE,
                voice_params=VoiceParams(),
            )
            response = await self._client.get(
                f"{self._base_url}{_PIPER_HEALTH_PATH}", params=params
            )
            return response.is_success
        except httpx.HTTPError:
            return False

    def backend_name(self) -> str:
        """Return 'piper'."""
        return _BACKEND_NAME


def _build_query_params(text: str, voice_params: VoiceParams) -> dict[str, str]:
    """Build Piper GET query parameters from text and voice config.

    Args:
        text: The utterance to synthesize.
        voice_params: Voice configuration for this synthesis call.

    Returns:
        Dict of query params ready for httpx GET request.
    """
    params: dict[str, str] = {"text": text}
    speaker_id = _resolve_speaker_id(voice_params.voice_id)
    if speaker_id is not None:
        params["speaker_id"] = str(speaker_id)
    return params


def _resolve_speaker_id(voice_id: str) -> int | None:
    """Parse voice_id as an integer speaker_id, or return None for single-speaker models.

    Args:
        voice_id: Raw voice_id string from VoiceParams.

    Returns:
        Integer speaker_id if voice_id is int-parseable, None otherwise.
    """
    try:
        return int(voice_id)
    except ValueError:
        return None
