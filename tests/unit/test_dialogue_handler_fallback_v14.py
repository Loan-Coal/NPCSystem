"""
test_dialogue_handler_fallback_v14.py - Unit test for dialogue handler fallback recovery.

Does NOT: call live LLM services.

Dependencies injected: fake LLM client and monkeypatched context/mutation helpers.
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FALLBACK_PATH = str(_REPO_ROOT / "src" / "npc_engine" / "data" / "fallback_responses.json")
_CANNED_DIR = str(_REPO_ROOT / "prompts" / "canned")

pytest.importorskip("neo4j")

from npc_engine.api.schemas import DialogueRequest
from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler, LLM_VALIDATION_FAILURES_METRIC
from npc_engine.engines.dialogue.session_store import SessionStore
from npc_engine.engines.llm_config_models import (
    EngineModelConfig,
    EngineFallbackPolicy,
    EngineModelParams,
    EnginePromptRef,
    EngineTimeoutsMs,
)
from npc_engine.utils.metrics import get_counter_value, reset_metrics_registry


def _make_engine_model_config() -> EngineModelConfig:
    return EngineModelConfig(
        engine="dialogue",
        llm=EngineModelParams(
            backend="mock",
            model="mock",
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


class MinimalLLMClient:
    """Minimal fake client for DialogueHandler construction in tests."""

    async def generate(self, prompt: str, max_tokens: int, temperature: float, top_p=None, stop_sequences=None, system=None) -> str:
        return "ok"

    async def generate_structured(self, prompt: str, schema: dict[str, Any], max_tokens: int, top_p=None, stop_sequences=None, system=None) -> dict[str, Any]:
        return {"bad": "payload"}

    async def stream(self, prompt: str, max_tokens: int, temperature: float, top_p=None, stop_sequences=None, system=None) -> AsyncIterator[str]:
        if False:
            yield ""

    def model_name(self) -> str:
        return "mock"


class FakeEmotionUpdater:
    """Deterministic emotion updater for dialogue handler tests."""

    async def get_state(self, npc_id: str):
        return SimpleNamespace(label="neutral")

    async def apply_dialogue_mood(self, npc_id: str, mood_update: str | None):
        return SimpleNamespace(label=mood_update or "neutral", valence=0)


def setup_function() -> None:
    reset_metrics_registry()


@pytest.mark.asyncio
async def test_dialogue_handler_recovers_from_validation_failure(monkeypatch) -> None:
    """Dialogue handler should return fallback response when parser validation fails."""

    async def fake_build_serialized_context(**kwargs):
        return "{}"

    async def fake_apply_dialogue_relation_deltas(**kwargs) -> None:
        return None

    monkeypatch.setattr("npc_engine.engines.dialogue.dialogue_handler.build_serialized_context", fake_build_serialized_context)
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.build_dialogue_prompt",
        lambda request, serialized_context: "prompt",
    )
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.apply_dialogue_relation_deltas",
        fake_apply_dialogue_relation_deltas,
    )

    handler = DialogueHandler(
        session=None,
        settings=SimpleNamespace(
            LLM_FALLBACK_PATH=_FALLBACK_PATH,
            CANNED_RESPONSES_DIR=_CANNED_DIR,
            LOG_LLM_PROMPTS=False,
        ),
        llm_client=MinimalLLMClient(),
        llm_config=SimpleNamespace(),
        engine_model_config=_make_engine_model_config(),
        session_store=SessionStore(ttl_seconds=300, max_turns=10),
        emotion_updater=FakeEmotionUpdater(),
        embedding_index=None,
    )
    handler._llm.generate_response = AsyncMock(return_value={"bad": "payload"})

    response = await handler.handle(
        DialogueRequest(
            player_id="player_1",
            npc_id="npc_1",
            player_message="hello",
            location_id="loc_1",
            session_id="session_1",
        )
    )

    assert response.npc_response == "I need a moment to think."
    assert response.session_id == "session_1"
    assert get_counter_value(LLM_VALIDATION_FAILURES_METRIC, labels={"engine": "dialogue"}) == 1.0


@pytest.mark.asyncio
async def test_stream_passes_emotion_state_to_context_builder(monkeypatch) -> None:
    """Stream flow should include emotion context when building serialized context."""

    captured_kwargs: dict[str, Any] = {}

    async def fake_build_serialized_context(**kwargs):
        captured_kwargs.update(kwargs)
        return "{}"

    monkeypatch.setattr("npc_engine.engines.dialogue.dialogue_handler.build_serialized_context", fake_build_serialized_context)
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.build_dialogue_prompt",
        lambda request, serialized_context: "prompt",
    )

    handler = DialogueHandler(
        session=None,
        settings=SimpleNamespace(LLM_FALLBACK_PATH=_FALLBACK_PATH, LOG_LLM_PROMPTS=False),
        llm_client=MinimalLLMClient(),
        llm_config=SimpleNamespace(),
        engine_model_config=_make_engine_model_config(),
        session_store=SessionStore(ttl_seconds=300, max_turns=10),
        emotion_updater=FakeEmotionUpdater(),
        embedding_index=None,
    )
    handler._llm.stream_text = AsyncMock(return_value=["chunk"])

    chunks = await handler.stream(
        DialogueRequest(
            player_id="player_1",
            npc_id="npc_1",
            player_message="hello",
            location_id="loc_1",
            session_id="session_1",
        )
    )

    assert chunks == ["chunk"]
    assert captured_kwargs["emotion_state"] == {"current_mood": "neutral"}
