"""
test_llm_factory.py - Unit tests for LLM factory routing and adapter selection.

Does NOT: call external LLM services.

Dependencies injected: None.
"""

from npc_engine.config import Settings
from npc_engine.engines.llm.factory import create_llm_client
from npc_engine.engines.llm.mock_adapter import MockLLMAdapter
from npc_engine.engines.llm.ollama_adapter import OllamaAdapter


def _base_settings() -> dict:
    return {
        "API_KEY_SECRET": "npc_dev_secret_2026_alpha",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "password",
    }


def test_factory_returns_mock_adapter_for_mock_backend() -> None:
    settings = Settings(**{**_base_settings(), "LLM_BACKEND": "mock"})
    client = create_llm_client(settings=settings)
    assert isinstance(client, MockLLMAdapter)


def test_factory_requires_url_for_mistral_backend() -> None:
    settings = Settings(**{**_base_settings(), "LLM_BACKEND": "mistral7b", "MISTRAL_API_URL": None})
    try:
        create_llm_client(settings=settings)
        assert False, "Expected ValueError for missing MISTRAL_API_URL"
    except ValueError as error:
        assert "MISTRAL_API_URL" in str(error)


def test_factory_returns_ollama_adapter_for_ollama_backend() -> None:
    settings = Settings(**{**_base_settings(), "LLM_BACKEND": "ollama", "OLLAMA_MODEL": "mixtral:8x7b"})
    client = create_llm_client(settings=settings)
    assert isinstance(client, OllamaAdapter)


def test_factory_requires_non_empty_ollama_url() -> None:
    settings = Settings(**{**_base_settings(), "LLM_BACKEND": "ollama", "OLLAMA_API_URL": "", "OLLAMA_MODEL": "mixtral:8x7b"})
    try:
        create_llm_client(settings=settings)
        assert False, "Expected ValueError for missing OLLAMA_API_URL"
    except ValueError as error:
        assert "OLLAMA_API_URL" in str(error)


def test_factory_requires_non_empty_ollama_model() -> None:
    settings = Settings(**{**_base_settings(), "LLM_BACKEND": "ollama", "OLLAMA_MODEL": ""})
    try:
        create_llm_client(settings=settings)
        assert False, "Expected ValueError for missing OLLAMA_MODEL"
    except ValueError as error:
        assert "OLLAMA_MODEL" in str(error)
