"""
test_llm_factory.py - Unit tests for LLM factory routing and adapter selection.

Does NOT: call external LLM services.

Dependencies injected: None.
"""

from npc_engine.config import Settings
from npc_engine.engines.llm.factory import create_llm_client_for_engine
from npc_engine.engines.llm.mock_adapter import MockLLMAdapter
from npc_engine.engines.llm.ollama_adapter import OllamaAdapter
from npc_engine.engines.llm_config_models import (
    EngineModelConfig,
    EngineFallbackPolicy,
    EngineModelParams,
    EnginePromptRef,
    EngineTimeoutsMs,
)


def _base_settings() -> dict:
    return {
        "API_KEY_SECRET": "npc_dev_secret_2026_alpha",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "password",
    }


def _make_engine_config(backend: str, model: str = "test-model") -> EngineModelConfig:
    return EngineModelConfig(
        engine="dialogue",
        llm=EngineModelParams(
            backend=backend,
            model=model,
            temperature=0.7,
            max_tokens=512,
            top_p=0.95,
            stop_sequences=[],
        ),
        prompt=EnginePromptRef(name="dialogue_main", version=1),
        output_schema_ref="dialogue_response_v1",
        fallback=EngineFallbackPolicy(policy="graceful_degradation", tiers=["full", "graph_only", "canned"]),
        timeouts_ms=EngineTimeoutsMs(full=30000, graph_only=10000, canned=100),
    )


def test_factory_returns_mock_adapter_for_mock_backend() -> None:
    settings = Settings(**_base_settings())
    engine_config = _make_engine_config(backend="mock")
    client = create_llm_client_for_engine(engine_config=engine_config, settings=settings)
    assert isinstance(client, MockLLMAdapter)


def test_factory_returns_ollama_adapter_for_ollama_backend() -> None:
    settings = Settings(**_base_settings())
    engine_config = _make_engine_config(backend="ollama", model="mixtral:8x7b")
    client = create_llm_client_for_engine(engine_config=engine_config, settings=settings)
    assert isinstance(client, OllamaAdapter)


def test_factory_requires_non_empty_ollama_url() -> None:
    settings = Settings(**{**_base_settings(), "OLLAMA_API_URL": ""})
    engine_config = _make_engine_config(backend="ollama", model="mixtral:8x7b")
    try:
        create_llm_client_for_engine(engine_config=engine_config, settings=settings)
        assert False, "Expected ValueError for missing OLLAMA_API_URL"
    except ValueError as error:
        assert "OLLAMA_API_URL" in str(error)


def test_factory_uses_per_engine_model_name_for_ollama() -> None:
    settings = Settings(**_base_settings())
    engine_config = _make_engine_config(backend="ollama", model="llama3:70b")
    client = create_llm_client_for_engine(engine_config=engine_config, settings=settings)
    assert isinstance(client, OllamaAdapter)
    assert client.model_name() == "llama3:70b"


def test_factory_raises_for_unknown_backend() -> None:
    settings = Settings(**_base_settings())
    try:
        create_llm_client_for_engine.__wrapped__ if hasattr(create_llm_client_for_engine, "__wrapped__") else None
        # Directly test the raise path: mock the backend string on the config
        import unittest.mock as mock
        bad_config = mock.MagicMock()
        bad_config.llm.backend = "unknown_backend"
        bad_config.llm.model = "x"
        create_llm_client_for_engine(engine_config=bad_config, settings=settings)
        assert False, "Expected ValueError for unsupported backend"
    except ValueError as error:
        assert "unsupported" in str(error).lower() or "unknown_backend" in str(error)
