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
from npc_engine.services.input_moderation import build_input_moderation_service
from npc_engine.services.output_moderation import build_output_moderation_service
from npc_engine.engines.dialogue.session_store import SessionStore
from npc_engine.engines.llm_config_models import (
    EngineModelConfig,
    EngineFallbackPolicy,
    EngineModelParams,
    EnginePromptRef,
    EngineTimeoutsMs,
)
from npc_engine.utils.metrics import get_counter_value, reset_metrics_registry


@pytest.fixture(autouse=True)
def _default_archetype(monkeypatch):
    """Default the NPC archetype to None (→ 'default') so handler tests need no graph session."""
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.get_npc_archetype",
        AsyncMock(return_value=None),
    )
    # F1.1 wired a phase-transition write after the relation delta; these no-graph
    # tests use session=None, so stub the new call site to a no-op.
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.apply_phase_transition",
        AsyncMock(return_value=None),
    )


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

    def __init__(self) -> None:
        self.last_session = None
        self.last_tick: int = 0

    async def get_state(self, npc_id: str):
        return SimpleNamespace(label="neutral")

    async def apply_dialogue_mood(self, npc_id: str, mood_update: str | None, session=None, tick: int = 0):
        self.last_session = session
        self.last_tick = tick
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
        input_moderation=build_input_moderation_service("mature"),
        output_moderation=build_output_moderation_service("mature"),
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
async def test_validation_fallback_uses_npc_archetype_line(monkeypatch) -> None:
    """A non-default archetype NPC in the validation-fallback path returns its archetype line (ISSUE-081)."""

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
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.get_npc_archetype",
        AsyncMock(return_value="guard"),
    )

    handler = DialogueHandler(
        session=None,
        settings=SimpleNamespace(LLM_FALLBACK_PATH=_FALLBACK_PATH, CANNED_RESPONSES_DIR=_CANNED_DIR, LOG_LLM_PROMPTS=False),
        llm_client=MinimalLLMClient(),
        llm_config=SimpleNamespace(),
        engine_model_config=_make_engine_model_config(),
        session_store=SessionStore(ttl_seconds=300, max_turns=10),
        emotion_updater=FakeEmotionUpdater(),
        embedding_index=None,
        input_moderation=build_input_moderation_service("mature"),
        output_moderation=build_output_moderation_service("mature"),
    )
    handler._llm.generate_response = AsyncMock(return_value={"bad": "payload"})

    response = await handler.handle(
        DialogueRequest(
            player_id="player_1", npc_id="captain_sorn", player_message="hello",
            location_id="loc_1", session_id="session_1",
        )
    )

    assert response.npc_response == "Move along, citizen."


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
        input_moderation=build_input_moderation_service("mature"),
        output_moderation=build_output_moderation_service("mature"),
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


@pytest.mark.asyncio
async def test_apply_relation_and_emotion_passes_session_and_tick(monkeypatch) -> None:
    """DialogueHandler must pass session and tick to apply_dialogue_mood (EXP-14 slice-4)."""
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

    fake_session = object()
    fake_updater = FakeEmotionUpdater()

    handler = DialogueHandler(
        session=fake_session,
        settings=SimpleNamespace(
            LLM_FALLBACK_PATH=_FALLBACK_PATH,
            CANNED_RESPONSES_DIR=_CANNED_DIR,
            LOG_LLM_PROMPTS=False,
        ),
        llm_client=MinimalLLMClient(),
        llm_config=SimpleNamespace(),
        engine_model_config=_make_engine_model_config(),
        session_store=SessionStore(ttl_seconds=300, max_turns=10),
        emotion_updater=fake_updater,
        embedding_index=None,
        input_moderation=build_input_moderation_service("mature"),
        output_moderation=build_output_moderation_service("mature"),
    )

    await handler.handle(
        DialogueRequest(
            player_id="player_1",
            npc_id="npc_1",
            player_message="hello",
            location_id="loc_1",
            session_id="session_1",
        )
    )

    assert fake_updater.last_session is fake_session, (
        "apply_dialogue_mood must receive the Neo4j session so writes can be persisted"
    )
    assert fake_updater.last_tick != 0, (
        "apply_dialogue_mood must receive a non-zero tick_id"
    )
