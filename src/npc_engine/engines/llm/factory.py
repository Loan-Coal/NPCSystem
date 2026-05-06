"""
factory.py - Creates LLM adapter instances from per-engine config.

Does NOT: perform generation calls directly.

Dependencies injected: Settings, EngineModelConfig.
Used by: api.dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from npc_engine.config import Settings
from npc_engine.engines.llm.llama_adapter import LlamaAdapter
from npc_engine.engines.llm.mistral_adapter import MistralAdapter
from npc_engine.engines.llm.mock_adapter import MockLLMAdapter
from npc_engine.engines.llm.ollama_adapter import OllamaAdapter
from npc_engine.engines.llm.protocols import LLMClientProtocol

if TYPE_CHECKING:
    from npc_engine.engines.llm_config_models import EngineModelConfig


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
    model = engine_config.llm.model

    if backend == "mock":
        return MockLLMAdapter()
    if backend == "mistral7b":
        if settings.MISTRAL_API_URL is None:
            raise ValueError("MISTRAL_API_URL is required for mistral7b backend")
        return MistralAdapter(
            base_url=settings.MISTRAL_API_URL,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        )
    if backend == "llama8b":
        if settings.LLAMA_API_URL is None:
            raise ValueError("LLAMA_API_URL is required for llama8b backend")
        return LlamaAdapter(
            base_url=settings.LLAMA_API_URL,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        )
    if backend == "ollama":
        if settings.OLLAMA_API_URL.strip() == "":
            raise ValueError("OLLAMA_API_URL is required for ollama backend")
        return OllamaAdapter(
            base_url=settings.OLLAMA_API_URL,
            model_name=model,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        )
    raise ValueError(f"Unsupported backend declared in engine config: {backend}")
