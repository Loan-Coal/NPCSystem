"""
factory.py - Creates LLM adapter instances from configured backend keys.

Does NOT: perform generation calls directly.

Dependencies injected: Settings.
"""

from typing import Callable

from config import Settings
from engines.llm.llama_adapter import LlamaAdapter
from engines.llm.mistral_adapter import MistralAdapter
from engines.llm.mock_adapter import MockLLMAdapter
from engines.llm.ollama_adapter import OllamaAdapter
from engines.llm.protocols import LLMClientProtocol


def _create_mock(_: Settings) -> LLMClientProtocol:
    return MockLLMAdapter()


def _create_mistral(settings: Settings) -> LLMClientProtocol:
    if settings.MISTRAL_API_URL is None:
        raise ValueError("MISTRAL_API_URL is required for mistral7b backend")
    return MistralAdapter(
        base_url=settings.MISTRAL_API_URL,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
    )


def _create_llama(settings: Settings) -> LLMClientProtocol:
    if settings.LLAMA_API_URL is None:
        raise ValueError("LLAMA_API_URL is required for llama8b backend")
    return LlamaAdapter(
        base_url=settings.LLAMA_API_URL,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
    )


def _create_ollama(settings: Settings) -> LLMClientProtocol:
    if settings.OLLAMA_API_URL.strip() == "":
        raise ValueError("OLLAMA_API_URL is required for ollama backend")
    if settings.OLLAMA_MODEL.strip() == "":
        raise ValueError("OLLAMA_MODEL is required for ollama backend")
    return OllamaAdapter(
        base_url=settings.OLLAMA_API_URL,
        model_name=settings.OLLAMA_MODEL,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
    )


BACKEND_BUILDERS: dict[str, Callable[[Settings], LLMClientProtocol]] = {
    "mock": _create_mock,
    "mistral7b": _create_mistral,
    "llama8b": _create_llama,
    "ollama": _create_ollama,
}


def create_llm_client(settings: Settings) -> LLMClientProtocol:
    """Return backend adapter based on configuration."""

    builder = BACKEND_BUILDERS.get(settings.LLM_BACKEND)
    if builder is None:
        raise ValueError(f"Unsupported LLM_BACKEND: {settings.LLM_BACKEND}")
    return builder(settings)
