"""
test_per_engine_timeout_wiring.py — per-engine timeout threading (T8.2).

RED anchor: asserts
  (a) an engine declaring timeouts_ms.full: 30000 produces an adapter whose
      effective timeout is 30s, not the global 10s fallback;
  (b) every llm_config.yaml timeout field is consumed by the factory (no dead fields).

Both assertions fail today because factory always passes settings.LLM_TIMEOUT_SECONDS.

Does NOT: call external LLM services or touch the network.
"""
from __future__ import annotations

import pathlib
import unittest.mock as mock
from typing import Any

import yaml

from npc_engine.config import Settings
from npc_engine.engines.llm.admission_control import reset_default_gate
from npc_engine.engines.llm.factory import create_llm_client_for_engine
from npc_engine.engines.llm_config_models import (
    EngineModelConfig,
    EngineFallbackPolicy,
    EngineModelParams,
    EnginePromptRef,
    EngineTimeoutsMs,
)

_ENGINES_DIR = (
    pathlib.Path(__file__).resolve().parents[3]
    / "src"
    / "npc_engine"
    / "engines"
)

_BASE_SETTINGS: dict[str, Any] = {
    "API_KEY_SECRET": "npc_dev_secret_2026_alpha",
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USER": "neo4j",
    "NEO4J_PASSWORD": "password",
    "LLM_TIMEOUT_SECONDS": 10.0,  # global fallback — deliberately differs from per-engine values
}


def setup_function() -> None:
    """Reset the admission gate before each test to avoid cross-test state."""
    reset_default_gate()


def _ollama_config(full_ms: int, engine: str = "test") -> EngineModelConfig:
    """Build a minimal Ollama EngineModelConfig for the given full timeout."""
    return EngineModelConfig(
        engine=engine,
        llm=EngineModelParams(
            backend="ollama",
            model="qwen2.5:7b",
            temperature=0.5,
            max_tokens=150,
            top_p=0.9,
            stop_sequences=[],
        ),
        prompt=EnginePromptRef(name="chapter_label_v1", version="1"),
        output_schema_ref="chapter_label_response_v1",
        fallback=EngineFallbackPolicy(policy="graceful_degradation", tiers=["full"]),
        timeouts_ms=EngineTimeoutsMs(full=full_ms),
    )


def test_per_engine_full_timeout_overrides_global_for_ollama(monkeypatch: Any) -> None:
    """Ollama adapter must receive timeouts_ms.full / 1000, not LLM_TIMEOUT_SECONDS."""
    captured: dict[str, Any] = {}

    def _spy(**kwargs: Any) -> Any:
        captured.update(kwargs)
        from npc_engine.engines.llm.mock_adapter import MockLLMAdapter
        return MockLLMAdapter()

    monkeypatch.setattr("npc_engine.engines.llm.factory.OllamaAdapter", _spy)
    settings = Settings(**_BASE_SETTINGS)  # LLM_TIMEOUT_SECONDS=10.0

    create_llm_client_for_engine(
        engine_config=_ollama_config(full_ms=30000),
        settings=settings,
    )

    assert captured.get("timeout_seconds") == 30.0, (
        f"adapter timeout was {captured.get('timeout_seconds')!r}; "
        "expected 30.0s from timeouts_ms.full=30000, not the global 10s fallback"
    )


def test_per_engine_full_timeout_overrides_global_for_openai(monkeypatch: Any) -> None:
    """OpenAI adapter must receive timeouts_ms.full / 1000, not LLM_TIMEOUT_SECONDS."""
    captured: dict[str, Any] = {}

    def _spy(**kwargs: Any) -> Any:
        captured.update(kwargs)
        from npc_engine.engines.llm.mock_adapter import MockLLMAdapter
        return MockLLMAdapter()

    monkeypatch.setattr(
        "npc_engine.engines.llm.factory.OpenAICompatibleAdapter", _spy
    )
    settings = Settings(**{**_BASE_SETTINGS, "OPENAI_API_KEY": "sk-test"})

    engine_config = EngineModelConfig(
        engine="chapter",
        llm=EngineModelParams(
            backend="openai",
            model="gpt-4o",
            temperature=0.5,
            max_tokens=150,
            top_p=0.9,
            stop_sequences=[],
        ),
        prompt=EnginePromptRef(name="chapter_label_v1", version="1"),
        output_schema_ref="chapter_label_response_v1",
        fallback=EngineFallbackPolicy(policy="graceful_degradation", tiers=["full"]),
        timeouts_ms=EngineTimeoutsMs(full=45000),
    )

    create_llm_client_for_engine(engine_config=engine_config, settings=settings)

    assert captured.get("timeout_seconds") == 45.0, (
        f"adapter timeout was {captured.get('timeout_seconds')!r}; "
        "expected 45.0s from timeouts_ms.full=45000"
    )


def test_global_timeout_is_fallback_when_no_engine_timeout(monkeypatch: Any) -> None:
    """settings.LLM_TIMEOUT_SECONDS is used when timeouts_ms is absent."""
    captured: dict[str, Any] = {}

    def _spy(**kwargs: Any) -> Any:
        captured.update(kwargs)
        from npc_engine.engines.llm.mock_adapter import MockLLMAdapter
        return MockLLMAdapter()

    monkeypatch.setattr("npc_engine.engines.llm.factory.OllamaAdapter", _spy)
    settings = Settings(**{**_BASE_SETTINGS, "LLM_TIMEOUT_SECONDS": 7.5})

    engine_config_mock = mock.MagicMock()
    engine_config_mock.llm.backend = "ollama"
    engine_config_mock.llm.model = "qwen2.5:7b"
    engine_config_mock.engine = "test"
    engine_config_mock.timeouts_ms = None  # no per-engine timeout

    create_llm_client_for_engine(engine_config=engine_config_mock, settings=settings)

    assert captured.get("timeout_seconds") == 7.5, (
        f"expected global fallback 7.5s but got {captured.get('timeout_seconds')!r}"
    )


def test_every_yaml_timeout_field_is_consumed(monkeypatch: Any) -> None:
    """No llm_config.yaml may declare timeouts_ms.full that the factory ignores.

    For each engine yaml that declares timeouts_ms.full, verifies the created adapter
    receives exactly that value as its timeout_seconds (proving the field is consumed).
    """
    yaml_files = sorted(_ENGINES_DIR.rglob("llm_config.yaml"))
    assert yaml_files, "No llm_config.yaml files found — _ENGINES_DIR path is wrong"

    for yaml_path in yaml_files:
        raw: dict[str, Any] = yaml.safe_load(yaml_path.read_text())
        declared_ms = (raw.get("timeouts_ms") or {}).get("full")
        if declared_ms is None:
            continue  # engine opted out of per-engine timeout — skip

        captured: dict[str, Any] = {}

        def _make_spy(cap: dict[str, Any]) -> Any:
            def _spy(**kwargs: Any) -> Any:
                cap.update(kwargs)
                from npc_engine.engines.llm.mock_adapter import MockLLMAdapter
                return MockLLMAdapter()
            return _spy

        monkeypatch.setattr(
            "npc_engine.engines.llm.factory.OllamaAdapter", _make_spy(captured)
        )
        settings = Settings(**_BASE_SETTINGS)  # LLM_TIMEOUT_SECONDS=10.0 differs

        engine_cfg = EngineModelConfig.model_validate(raw)
        create_llm_client_for_engine(engine_config=engine_cfg, settings=settings)

        expected = declared_ms / 1000.0
        got = captured.get("timeout_seconds")
        assert got == expected, (
            f"{yaml_path.parent.name}/llm_config.yaml declares timeouts_ms.full={declared_ms} "
            f"but adapter got timeout_seconds={got!r} — field is not consumed by factory"
        )
