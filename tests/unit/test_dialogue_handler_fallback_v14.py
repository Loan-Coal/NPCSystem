"""
test_dialogue_handler_fallback_v14.py - Unit test for dialogue handler fallback recovery.

Does NOT: call live LLM services; open Neo4j sessions.

Dependencies injected: fake LLM client, mock DialogueGraphPort, mock DialogueContextPort.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FALLBACK_PATH = str(_REPO_ROOT / "src" / "npc_engine" / "data" / "fallback_responses.json")
_CANNED_DIR = str(_REPO_ROOT / "prompts" / "canned")

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
        self.last_tick: int = 0

    async def get_state(self, npc_id: str):
        return SimpleNamespace(label="neutral")

    async def apply_dialogue_mood(self, npc_id: str, mood_update: str | None, tick: int = 0):
        self.last_tick = tick
        return SimpleNamespace(label=mood_update or "neutral", valence=0)


@pytest.fixture()
def mock_dialogue_repo() -> MagicMock:
    """Mock DialogueGraphPort — no session held."""
    repo = AsyncMock()
    repo.get_npc_archetype = AsyncMock(return_value=None)
    repo.get_npc_voice_descriptor = AsyncMock(return_value=None)
    repo.get_world_state = AsyncMock(return_value=None)
    repo.apply_relation_deltas = AsyncMock(return_value=None)
    repo.set_routine_override = AsyncMock(return_value=None)
    return repo


@pytest.fixture()
def mock_dialogue_context() -> MagicMock:
    """Mock DialogueContextPort returning empty context string."""
    ctx = AsyncMock()
    ctx.build_context = AsyncMock(return_value="{}")
    return ctx


def _make_handler(
    emotion_updater=None,
    mock_dialogue_repo=None,
    mock_dialogue_context=None,
    extra_settings=None,
) -> DialogueHandler:
    """Build a minimal DialogueHandler for tests."""
    settings_ns = {
        "LLM_FALLBACK_PATH": _FALLBACK_PATH,
        "CANNED_RESPONSES_DIR": _CANNED_DIR,
        "LOG_LLM_PROMPTS": False,
    }
    if extra_settings:
        settings_ns.update(extra_settings)
    return DialogueHandler(
        settings=SimpleNamespace(**settings_ns),
        llm_client=MinimalLLMClient(),
        llm_config=SimpleNamespace(),
        engine_model_config=_make_engine_model_config(),
        session_store=SessionStore(ttl_seconds=300, max_turns=10),
        emotion_updater=emotion_updater or FakeEmotionUpdater(),
        input_moderation=build_input_moderation_service("mature"),
        output_moderation=build_output_moderation_service("mature"),
        dialogue_repo=mock_dialogue_repo or AsyncMock(),
        dialogue_context=mock_dialogue_context or AsyncMock(build_context=AsyncMock(return_value="{}")),
    )


def setup_function() -> None:
    reset_metrics_registry()


@pytest.mark.asyncio
async def test_dialogue_handler_recovers_from_validation_failure(
    mock_dialogue_repo,
    mock_dialogue_context,
    monkeypatch,
) -> None:
    """Dialogue handler should return fallback response when parser validation fails."""
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.build_dialogue_prompt",
        lambda request, serialized_context: "prompt",
    )
    handler = _make_handler(
        mock_dialogue_repo=mock_dialogue_repo,
        mock_dialogue_context=mock_dialogue_context,
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
async def test_validation_fallback_uses_npc_archetype_line(
    mock_dialogue_repo,
    mock_dialogue_context,
    monkeypatch,
) -> None:
    """A non-default archetype NPC in the validation-fallback path returns its archetype line."""
    mock_dialogue_repo.get_npc_archetype = AsyncMock(return_value="guard")
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.build_dialogue_prompt",
        lambda request, serialized_context: "prompt",
    )
    handler = _make_handler(
        mock_dialogue_repo=mock_dialogue_repo,
        mock_dialogue_context=mock_dialogue_context,
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
async def test_stream_passes_emotion_state_to_context_builder(
    mock_dialogue_repo,
    mock_dialogue_context,
    monkeypatch,
) -> None:
    """Stream flow should include emotion context when building serialized context."""
    captured_kwargs: dict[str, Any] = {}

    async def fake_build_context(**kwargs):
        captured_kwargs.update(kwargs)
        return "{}"

    mock_dialogue_context.build_context = fake_build_context
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.build_dialogue_prompt",
        lambda request, serialized_context: "prompt",
    )
    handler = _make_handler(
        mock_dialogue_repo=mock_dialogue_repo,
        mock_dialogue_context=mock_dialogue_context,
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
async def test_apply_relation_and_emotion_passes_tick(
    mock_dialogue_repo,
    mock_dialogue_context,
    monkeypatch,
) -> None:
    """DialogueHandler must pass tick to apply_dialogue_mood."""
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.build_dialogue_prompt",
        lambda request, serialized_context: "prompt",
    )
    fake_updater = FakeEmotionUpdater()
    handler = _make_handler(
        emotion_updater=fake_updater,
        mock_dialogue_repo=mock_dialogue_repo,
        mock_dialogue_context=mock_dialogue_context,
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

    assert fake_updater.last_tick != 0, (
        "apply_dialogue_mood must receive a non-zero tick_id"
    )
