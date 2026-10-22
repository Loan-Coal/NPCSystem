"""
test_relation_delta_clamping.py - Out-of-range LLM deltas are clamped, not zeroed.

Why this exists: the LLM occasionally returns relation_deltas outside [-15, 15].
Before the fix, Pydantic rejected the field and validation fell back to the canned
path, which always emits {0, 0, 0}. The correct behaviour is to clamp to [-15, 15]
so the relational movement is preserved (T25.5).

Does NOT: call LLM services or open Neo4j sessions.

Dependencies injected: stub LLM, mock dialogue repo.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, call

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FALLBACK_PATH = str(_REPO_ROOT / "src" / "npc_engine" / "data" / "fallback_responses.json")
_CANNED_DIR = str(_REPO_ROOT / "prompts" / "canned")

from npc_engine.api.schemas import DialogueRequest
from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler
from npc_engine.engines.dialogue.dialogue_models import DialogueGeneration, RelationDeltas
from npc_engine.services.input_moderation import build_input_moderation_service
from npc_engine.services.output_moderation import build_output_moderation_service
from npc_engine.engines.dialogue.session_store import SessionStore
from npc_engine.scheduler.game_clock import GameClock
from npc_engine.engines.llm_config_models import (
    EngineModelConfig,
    EngineFallbackPolicy,
    EngineModelParams,
    EnginePromptRef,
    EngineTimeoutsMs,
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
        prompt=EnginePromptRef(name="dialogue_main", version="v1"),
        output_schema_ref="dialogue_response_v1",
        fallback=EngineFallbackPolicy(policy="graceful_degradation", tiers=["full", "graph_only", "canned"]),
        timeouts_ms=EngineTimeoutsMs(full=30000, graph_only=10000, canned=100),
    )


class _OutOfRangeLLMClient:
    """Stub LLM that returns a delta above the declared ±15 bound."""

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        return {
            "npc_response": "You have been most helpful.",
            "relation_deltas": {"trust": 20, "fear": -25, "affection": 5},
        }

    async def generate(self, prompt: str, max_tokens: int, temperature: float, top_p=None, stop_sequences=None, system=None, seed=None) -> str:
        return "ok"

    async def stream(self, prompt: str, max_tokens: int, temperature: float, top_p=None, stop_sequences=None, system=None, seed=None) -> AsyncIterator[str]:
        if False:
            yield ""

    def model_name(self) -> str:
        return "mock-out-of-range"


class _FakeEmotionUpdater:
    async def get_state(self, npc_id: str) -> SimpleNamespace:
        return SimpleNamespace(label="neutral")

    async def apply_dialogue_mood(self, npc_id: str, mood_update: str | None, tick: int = 0) -> SimpleNamespace:
        return SimpleNamespace(label=mood_update or "neutral", valence=0)


def _make_handler(llm_client: Any, repo: Any) -> DialogueHandler:
    return DialogueHandler(
        settings=SimpleNamespace(
            LLM_FALLBACK_PATH=_FALLBACK_PATH,
            CANNED_RESPONSES_DIR=_CANNED_DIR,
            LOG_LLM_PROMPTS=False,
        ),
        llm_client=llm_client,
        llm_config=SimpleNamespace(),
        engine_model_config=_make_engine_model_config(),
        session_store=SessionStore(ttl_seconds=300, max_turns=10),
        emotion_updater=_FakeEmotionUpdater(),
        input_moderation=build_input_moderation_service("mature"),
        output_moderation=build_output_moderation_service("mature"),
        dialogue_repo=repo,
        dialogue_context=AsyncMock(build_context=AsyncMock(return_value=("{}", [], None))),
        clock=GameClock(mode="game_driven"),
    )


# ---------------------------------------------------------------------------
# Model-level tests
# ---------------------------------------------------------------------------


def test_relation_deltas_clamps_positive_overflow() -> None:
    """Values above +15 are clamped to +15, not rejected."""
    deltas = RelationDeltas.model_validate({"trust": 20, "fear": 0, "affection": 15})

    assert deltas.trust == 15
    assert deltas.fear == 0
    assert deltas.affection == 15


def test_relation_deltas_clamps_negative_overflow() -> None:
    """Values below -15 are clamped to -15, not rejected."""
    deltas = RelationDeltas.model_validate({"trust": 0, "fear": -25, "affection": -100})

    assert deltas.trust == 0
    assert deltas.fear == -15
    assert deltas.affection == -15


def test_dialogue_generation_survives_out_of_range_deltas() -> None:
    """DialogueGeneration must not raise ValidationError when LLM over-shoots."""
    generated = DialogueGeneration.model_validate({
        "npc_response": "Well met.",
        "relation_deltas": {"trust": 20, "fear": -20, "affection": 5},
    })

    assert generated.relation_deltas.trust == 15
    assert generated.relation_deltas.fear == -15
    assert generated.relation_deltas.affection == 5


# ---------------------------------------------------------------------------
# Handler-level test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_out_of_range_delta_is_clamped_and_applied_not_zeroed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An out-of-range LLM delta must reach apply_relation_deltas clamped, not as zeros.

    Before the fix: ValidationError → two retries → fallback → {0, 0, 0}.
    After the fix: clamp → valid model → apply with trust=15, fear=-15.
    """
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.build_dialogue_prompt",
        lambda request, serialized_context: "prompt",
    )
    repo = AsyncMock()
    repo.get_npc_archetype = AsyncMock(return_value=None)
    repo.get_npc_voice_descriptor = AsyncMock(return_value=None)
    repo.get_world_state = AsyncMock(return_value=None)
    repo.apply_relation_deltas = AsyncMock(return_value=None)
    repo.set_routine_override = AsyncMock(return_value=None)

    handler = _make_handler(llm_client=_OutOfRangeLLMClient(), repo=repo)

    await handler.handle(
        DialogueRequest(
            player_id="player_1",
            npc_id="npc_1",
            player_message="hello",
            location_id="loc_1",
            session_id="session_1",
        )
    )

    repo.apply_relation_deltas.assert_called_once()
    applied_deltas = repo.apply_relation_deltas.call_args.kwargs["relation_deltas"]
    assert applied_deltas.trust == 15, (
        f"Expected clamped trust=15, got {applied_deltas.trust} (zeros mean fallback fired)"
    )
    assert applied_deltas.fear == -15, (
        f"Expected clamped fear=-15, got {applied_deltas.fear} (zeros mean fallback fired)"
    )
    assert applied_deltas.affection == 5
