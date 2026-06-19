"""
Module: tts.factory
Layer: engines
Purpose: Registry + factory for TTSClientProtocol backends. New backends register
         via register_tts_backend(name, ctor) without editing existing code (OCP).
         build_tts_client dispatches via the registry, returning None when TTS is
         disabled. Mirrors the LLM register_backend() pattern in engines/llm/factory.py.
Does NOT: implement any TTS synthesis; delegates to adapter constructors.
Dependencies injected: Settings (TTS_ENABLED, TTS_BACKEND, PIPER_BASE_URL, etc.).
Used by: api/dependencies.get_tts_client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from npc_engine.engines.tts.mock_adapter import MockTTSAdapter
from npc_engine.engines.tts.piper_adapter import PiperAdapter
from npc_engine.engines.tts.protocols import TTSClientProtocol

if TYPE_CHECKING:
    from npc_engine.config import Settings

# Registry of (Settings) → TTSClientProtocol builders keyed by TTS_BACKEND name.
# Add new backends via register_tts_backend; never edit this dict directly.
_TTS_REGISTRY: dict[str, Callable[..., TTSClientProtocol]] = {}


def register_tts_backend(
    name: str, constructor: Callable[..., TTSClientProtocol]
) -> None:
    """Register a TTS backend constructor under *name*.

    Args:
        name: The TTS_BACKEND config value that selects this backend.
        constructor: Callable(settings) → TTSClientProtocol.
    """
    _TTS_REGISTRY[name] = constructor


def registered_tts_backends() -> frozenset[str]:
    """Return the names of all currently-registered TTS backends.

    Returns:
        Frozenset of backend names (single source of truth for config validation).
    """
    return frozenset(_TTS_REGISTRY)


def build_tts_client(settings: Settings) -> TTSClientProtocol | None:
    """Construct a TTS adapter from settings, or return None if TTS is disabled.

    Args:
        settings: Application settings providing TTS_ENABLED, TTS_BACKEND,
            PIPER_BASE_URL, TTS_TIMEOUT_SECONDS, etc.

    Returns:
        Configured TTSClientProtocol instance, or None when TTS_ENABLED is False.

    Raises:
        ValueError: When TTS_ENABLED is True but TTS_BACKEND names an unregistered
            backend.
    """
    if not settings.TTS_ENABLED:
        return None
    constructor = _TTS_REGISTRY.get(settings.TTS_BACKEND)
    if constructor is None:
        raise ValueError(
            f"Unknown TTS backend {settings.TTS_BACKEND!r}; "
            f"registered: {sorted(registered_tts_backends())}"
        )
    return constructor(settings)


# ---------------------------------------------------------------------------
# Built-in registrations (add new backends below — never remove existing ones)
# ---------------------------------------------------------------------------


def _build_piper(settings: Settings) -> TTSClientProtocol:
    return PiperAdapter(
        base_url=settings.PIPER_BASE_URL,
        timeout_seconds=settings.TTS_TIMEOUT_SECONDS,
    )


def _build_mock(settings: Settings) -> TTSClientProtocol:
    return MockTTSAdapter()


register_tts_backend("piper", _build_piper)
register_tts_backend("mock", _build_mock)
