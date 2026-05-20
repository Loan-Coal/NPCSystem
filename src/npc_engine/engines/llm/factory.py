"""
factory.py - Creates LLM adapter instances from per-engine config.

Does NOT: perform generation calls directly.

Dependencies injected: Settings, EngineModelConfig.
Used by: api.dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from npc_engine.config import Settings
from npc_engine.engines.llm.llama_adapter import LlamaAdapter
from npc_engine.engines.llm.mistral_adapter import MistralAdapter
from npc_engine.engines.llm.mock_adapter import MockLLMAdapter
from npc_engine.engines.llm.ollama_adapter import OllamaAdapter
from npc_engine.engines.llm.protocols import LLMClientProtocol

if TYPE_CHECKING:
    from npc_engine.engines.llm_config_models import EngineModelConfig


_REGISTRY: dict[str, Callable[..., LLMClientProtocol]] = {}


def register_backend(name: str, constructor: Callable[..., LLMClientProtocol]) -> None:
    """Register a backend constructor under the given name."""
    _REGISTRY[name] = constructor


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


def _build_mistral7b(engine_config: EngineModelConfig, settings: Settings) -> LLMClientProtocol:
    if settings.MISTRAL_API_URL is None:
        raise ValueError("MISTRAL_API_URL is required for mistral7b backend")
    return MistralAdapter(
        base_url=settings.MISTRAL_API_URL,
        model_name=engine_config.llm.model,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
    )


def _build_llama8b(engine_config: EngineModelConfig, settings: Settings) -> LLMClientProtocol:
    if settings.LLAMA_API_URL is None:
        raise ValueError("LLAMA_API_URL is required for llama8b backend")
    return LlamaAdapter(
        base_url=settings.LLAMA_API_URL,
        model_name=engine_config.llm.model,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
    )


def _build_ollama(engine_config: EngineModelConfig, settings: Settings) -> LLMClientProtocol:
    if settings.OLLAMA_API_URL.strip() == "":
        raise ValueError("OLLAMA_API_URL is required for ollama backend")
    return OllamaAdapter(
        base_url=settings.OLLAMA_API_URL,
        model_name=engine_config.llm.model,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
    )


register_backend("mock", _build_mock)
register_backend("mistral7b", _build_mistral7b)
register_backend("llama8b", _build_llama8b)
register_backend("ollama", _build_ollama)
