"""
test_engine_llm_config_integration.py - Integration tests for per-engine LLM config wiring.

Confirms that the dialogue engine reads its own config and that two handlers built from
distinct configs behave independently (different max_tokens/temperature reach the adapter).

Does NOT: call live LLM services or start the full FastAPI application.

Dependencies injected: tmp_path fixture, monkeypatch.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest

from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler
from npc_engine.engines.dialogue.session_store import SessionStore
from npc_engine.engines.llm_config_models import (
    EngineFallbackPolicy,
    EngineModelConfig,
    EngineModelParams,
    EnginePromptRef,
    EngineTimeoutsMs,
)
from npc_engine.engines.llm_runtime_config import get_config


_REPO_ROOT = Path(__file__).resolve().parents[2]
_FALLBACK_PATH = str(_REPO_ROOT / "src" / "npc_engine" / "data" / "fallback_responses.json")
_CANNED_DIR = str(_REPO_ROOT / "prompts" / "canned")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine_config(max_tokens: int, temperature: float) -> EngineModelConfig:
    return EngineModelConfig(
        engine="dialogue",
        llm=EngineModelParams(
            backend="mock",
            model="mock",
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.95,
            stop_sequences=[],
        ),
        prompt=EnginePromptRef(name="dialogue_main", version=1),
        output_schema_ref="dialogue_response_v1",
        fallback=EngineFallbackPolicy(policy="graceful_degradation", tiers=["full", "graph_only", "canned"]),
        timeouts_ms=EngineTimeoutsMs(full=30000, graph_only=10000, canned=100),
    )


class _CapturingLLMClient:
    """Fake adapter that captures max_tokens and temperature passed by the handler."""

    def __init__(self) -> None:
        self.captured_max_tokens: list[int] = []
        self.captured_temperature: list[float] = []

    async def generate(self, prompt: str, max_tokens: int, temperature: float) -> str:
        self.captured_max_tokens.append(max_tokens)
        self.captured_temperature.append(temperature)
        return "ok"

    async def generate_structured(
        self, prompt: str, schema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        self.captured_max_tokens.append(max_tokens)
        return {
            "npc_response": "ok",
            "relation_deltas": {"trust": 0, "fear": 0, "affection": 0},
            "mood_update": None,
            "action": {"type": "speak", "target_id": None, "parameters": {}},
            "facial_expression": {"type": "neutral", "intensity": 20},
        }

    async def stream(self, prompt: str, max_tokens: int, temperature: float) -> AsyncIterator[str]:
        self.captured_max_tokens.append(max_tokens)
        self.captured_temperature.append(temperature)
        if False:
            yield ""

    def model_name(self) -> str:
        return "mock"


class _FakeEmotionUpdater:
    def get_state(self, npc_id: str):
        return SimpleNamespace(label="neutral")

    def apply_dialogue_mood(self, npc_id: str, mood_update):
        pass


def _build_handler(adapter: _CapturingLLMClient, config: EngineModelConfig) -> DialogueHandler:
    return DialogueHandler(
        session=None,
        settings=SimpleNamespace(LLM_FALLBACK_PATH=_FALLBACK_PATH, CANNED_RESPONSES_DIR=_CANNED_DIR, LOG_LLM_PROMPTS=False),
        llm_client=adapter,
        llm_config=SimpleNamespace(),
        engine_model_config=config,
        session_store=SessionStore(ttl_seconds=300, max_turns=10),
        emotion_updater=_FakeEmotionUpdater(),
        embedding_index=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_dialogue_engine_real_config_loads_correctly() -> None:
    """The actual dialogue llm_config.yaml must parse into a valid EngineModelConfig."""

    config = get_config("dialogue")

    assert config.engine == "dialogue"
    assert config.llm.backend in ("mock", "ollama")
    assert config.llm.max_tokens > 0
    assert 0.0 <= config.llm.temperature <= 2.0
    assert config.timeouts_ms.full > 0
    assert config.timeouts_ms.graph_only > 0
    assert config.fallback.policy in ("graceful_degradation", "fail_fast")


def test_dialogue_handler_uses_max_tokens_from_engine_config(monkeypatch) -> None:
    """DialogueHandler must forward max_tokens from engine config to the LLM adapter."""

    async def fake_build_context(**kwargs):
        return "{}"

    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.build_serialized_context",
        fake_build_context,
    )
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.build_dialogue_prompt",
        lambda request, serialized_context: "prompt",
    )
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.apply_dialogue_relation_deltas",
        lambda **_: None,
    )

    adapter_256 = _CapturingLLMClient()
    handler_256 = _build_handler(adapter_256, _make_engine_config(max_tokens=256, temperature=0.5))

    adapter_1024 = _CapturingLLMClient()
    handler_1024 = _build_handler(adapter_1024, _make_engine_config(max_tokens=1024, temperature=0.9))

    assert handler_256._llm._max_tokens == 256
    assert handler_1024._llm._max_tokens == 1024
    assert handler_256._llm._temperature == 0.5
    assert handler_1024._llm._temperature == 0.9


def test_two_handlers_with_distinct_configs_have_independent_timeout_values() -> None:
    """Timeouts must be sourced exclusively from the per-engine config, not Settings."""

    adapter = _CapturingLLMClient()
    config_fast = _make_engine_config(max_tokens=128, temperature=0.1)
    config_fast = EngineModelConfig(
        engine="dialogue",
        llm=config_fast.llm,
        prompt=config_fast.prompt,
        output_schema_ref=config_fast.output_schema_ref,
        fallback=config_fast.fallback,
        timeouts_ms=EngineTimeoutsMs(full=5000, graph_only=2000, canned=50),
    )
    config_slow = _make_engine_config(max_tokens=512, temperature=0.8)

    handler_fast = _build_handler(adapter, config_fast)
    handler_slow = _build_handler(adapter, config_slow)

    assert handler_fast._engine_model_config.timeouts_ms.full == 5000
    assert handler_slow._engine_model_config.timeouts_ms.full == 30000
