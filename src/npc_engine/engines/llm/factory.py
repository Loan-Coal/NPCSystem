"""
factory.py - Creates LLM adapter instances from per-engine config.
Layer: engines
Purpose: Registry of LLM backend constructors keyed by name; builds the adapter
         declared by a per-engine config.
Does NOT: perform generation calls directly.
Dependencies injected: Settings, EngineModelConfig.
Used by: api.dependencies, engines.llm_config_models (backend validation).

Extension point (OCP): add a new local/remote LLM backend by writing an adapter
that satisfies LLMClientProtocol and calling register_backend("name", ctor) at
import time, then importing it from engines/llm/__init__.py so registration runs
on package import. Config validation (llm_config_models) accepts any registered
backend, so no Literal needs editing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from npc_engine.config import Settings
from npc_engine.engines.llm.mock_adapter import MockLLMAdapter
from npc_engine.engines.llm.ollama_adapter import OllamaAdapter
from npc_engine.engines.llm.protocols import LLMClientProtocol

if TYPE_CHECKING:
    from npc_engine.engines.llm_config_models import EngineModelConfig


_REGISTRY: dict[str, Callable[..., LLMClientProtocol]] = {}


def register_backend(name: str, constructor: Callable[..., LLMClientProtocol]) -> None:
    """Register a backend constructor under the given name."""
    _REGISTRY[name] = constructor


def registered_backends() -> frozenset[str]:
    """Return the set of currently-registered backend names.

    Single source of truth for which backends are valid: config validation checks
    against this rather than a hardcoded Literal, so a registered backend is always
    accepted and an unregistered one fails at config load (not at first generate).
    """
    return frozenset(_REGISTRY)


def create_llm_client_for_engine(
    engine_config: EngineModelConfig,
    settings: Settings,
) -> LLMClientProtocol:
    """Return a backend adapter configured from a per-engine LLM config.

    The backend type is taken from ``engine_config.llm.backend``; connection
    parameters (URLs, global timeout) are taken from ``settings``.  For the
    Ollama backend the model name comes from ``engine_config.llm.model``,
    enabling per-engine model selection.

    Args:
        engine_config: Validated per-engine LLM configuration.
        settings: Application settings providing backend URLs and timeout.

    Returns:
        Concrete LLMClientProtocol for the engine's declared backend.

    Raises:
        ValueError: If the backend declared in engine_config is unsupported or
            a required URL setting is missing.
    """
    backend = engine_config.llm.backend
    constructor = _REGISTRY.get(backend)
    if constructor is None:
        raise ValueError(f"Unsupported LLM backend: {backend!r}")
    return constructor(engine_config=engine_config, settings=settings)


def _build_mock(engine_config: EngineModelConfig, settings: Settings) -> LLMClientProtocol:
    return MockLLMAdapter()


def _build_ollama(engine_config: EngineModelConfig, settings: Settings) -> LLMClientProtocol:
    if settings.OLLAMA_API_URL.strip() == "":
        raise ValueError("OLLAMA_API_URL is required for ollama backend")
    return OllamaAdapter(
        base_url=settings.OLLAMA_API_URL,
        model_name=engine_config.llm.model,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
    )


register_backend("mock", _build_mock)
register_backend("ollama", _build_ollama)
