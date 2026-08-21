"""
test_dialogue_handler_clock_tick.py - Regression tests for ISSUE-165.

DialogueHandler used to stamp graph writes with int(datetime.now().timestamp()), so
"5 ticks" meant 5 real seconds and two turns in the same game tick disagreed. These
tests pin the tick to the injected ClockPort instead.

Does NOT: call live LLM services; open Neo4j sessions; advance the clock itself.

Dependencies injected: fake LLM client, mock DialogueGraphPort/DialogueContextPort,
                       a real GameClock (satisfies ClockPort).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FALLBACK_PATH = str(_REPO_ROOT / "src" / "npc_engine" / "data" / "fallback_responses.json")
_CANNED_DIR = str(_REPO_ROOT / "prompts" / "canned")

from npc_engine.api.schemas import DialogueRequest
from npc_engine.engines.dialogue.dialogue_handler import (
    LOW_VALENCE_ROUTINE_OVERRIDE_TICKS,
    DialogueHandler,
)
from npc_engine.engines.dialogue.session_store import SessionStore
from npc_engine.engines.llm_config_models import (
    EngineFallbackPolicy,
    EngineModelConfig,
    EngineModelParams,
    EnginePromptRef,
    EngineTimeoutsMs,
)
from npc_engine.scheduler.game_clock import GameClock
from npc_engine.services.input_moderation import build_input_moderation_service
from npc_engine.services.output_moderation import build_output_moderation_service


def _make_engine_model_config() -> EngineModelConfig:
    return EngineModelConfig(
        engine="dialogue",
        llm=EngineModelParams(
            backend="mock", model="mock", temperature=0.7,
            max_tokens=512, top_p=0.95, stop_sequences=[],
        ),
        prompt=EnginePromptRef(name="dialogue_main", version="v1"),
        output_schema_ref="dialogue_response_v1",
        fallback=EngineFallbackPolicy(policy="graceful_degradation", tiers=["full", "graph_only", "canned"]),
        timeouts_ms=EngineTimeoutsMs(full=30000, graph_only=10000, canned=100),
    )


class _MinimalLLMClient:
    """Minimal fake client — always fails validation so the canned path is deterministic."""

    async def generate(self, prompt: str, max_tokens: int, temperature: float, top_p=None,
                       stop_sequences=None, system=None, seed=None) -> str:
        return "ok"

    async def generate_structured(self, prompt: str, schema: dict[str, Any], max_tokens: int,
                                  top_p=None, stop_sequences=None, system=None, seed=None) -> dict[str, Any]:
        return {"bad": "payload"}

    async def stream(self, prompt: str, max_tokens: int, temperature: float, top_p=None,
                     stop_sequences=None, system=None, seed=None) -> AsyncIterator[str]:
        if False:
            yield ""

    def model_name(self) -> str:
        return "mock"


class _RecordingEmotionUpdater:
    """Records every tick handed to apply_dialogue_mood, and the valence it returns."""

    def __init__(self, valence: int = 0) -> None:
        self.ticks: list[int] = []
        self._valence = valence

    async def get_state(self, npc_id: str):
        return SimpleNamespace(label="neutral")

    async def apply_dialogue_mood(self, npc_id: str, mood_update: str | None, tick: int):
        self.ticks.append(tick)
        return SimpleNamespace(label=mood_update or "neutral", valence=self._valence, arousal=0)


def _make_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_npc_archetype = AsyncMock(return_value=None)
    repo.get_npc_voice_descriptor = AsyncMock(return_value=None)
    repo.get_world_state = AsyncMock(return_value=None)
    repo.apply_relation_deltas = AsyncMock(return_value=None)
    repo.set_routine_override = AsyncMock(return_value=None)
    return repo


def _make_handler(*, clock: GameClock, emotion_updater, repo) -> DialogueHandler:
    """Build a minimal DialogueHandler wired to a real GameClock."""
    return DialogueHandler(
        settings=SimpleNamespace(
            LLM_FALLBACK_PATH=_FALLBACK_PATH,
            CANNED_RESPONSES_DIR=_CANNED_DIR,
            LOG_LLM_PROMPTS=False,
        ),
        llm_client=_MinimalLLMClient(),
        llm_config=SimpleNamespace(),
        engine_model_config=_make_engine_model_config(),
        session_store=SessionStore(ttl_seconds=300, max_turns=10),
        emotion_updater=emotion_updater,
        input_moderation=build_input_moderation_service("mature"),
        output_moderation=build_output_moderation_service("mature"),
        dialogue_repo=repo,
        dialogue_context=AsyncMock(build_context=AsyncMock(return_value=("{}", [], None))),
        clock=clock,
    )


def _request(message: str = "hello") -> DialogueRequest:
    return DialogueRequest(
        player_id="player_1", npc_id="npc_1", player_message=message,
        location_id="loc_1", session_id="session_1",
    )


@pytest.fixture(autouse=True)
def _stub_prompt(monkeypatch):
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.build_dialogue_prompt",
        lambda request, serialized_context: "prompt",
    )


# ---------------------------------------------------------------------------
# The regression ISSUE-165 names explicitly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_turns_at_same_game_tick_write_same_emotion_tick() -> None:
    """Two dialogue turns at one game tick must stamp the same emotion_updated_at_tick.

    Previously each turn read the wall clock, so the two writes disagreed whenever the
    turns straddled a second boundary.
    """
    clock = GameClock(mode="game_driven")
    await clock.advance(tick_delta=7, time_delta_seconds=0)
    updater = _RecordingEmotionUpdater()
    handler = _make_handler(clock=clock, emotion_updater=updater, repo=_make_repo())

    await handler.handle(_request("hello"))
    await handler.handle(_request("hello again"))

    assert updater.ticks == [7, 7]


@pytest.mark.asyncio
async def test_dialogue_tick_advances_with_the_game_clock() -> None:
    """Advancing the clock between turns must move the stamped tick by the same amount."""
    clock = GameClock(mode="game_driven")
    updater = _RecordingEmotionUpdater()
    handler = _make_handler(clock=clock, emotion_updater=updater, repo=_make_repo())

    await handler.handle(_request("first"))
    await clock.advance(tick_delta=1, time_delta_seconds=0)
    await handler.handle(_request("second"))

    assert updater.ticks[1] == updater.ticks[0] + 1


@pytest.mark.asyncio
async def test_relation_deltas_and_emotion_share_one_authoritative_tick() -> None:
    """All writes in a turn must come from a single clock read, not several."""
    clock = GameClock(mode="game_driven")
    await clock.advance(tick_delta=11, time_delta_seconds=0)
    updater = _RecordingEmotionUpdater()
    repo = _make_repo()
    handler = _make_handler(clock=clock, emotion_updater=updater, repo=repo)

    await handler.handle(_request())

    assert updater.ticks == [11]
    assert repo.apply_relation_deltas.await_args.kwargs["tick_id"] == 11


# ---------------------------------------------------------------------------
# Routine override expiry is denominated in game ticks, not seconds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_routine_override_expires_in_game_ticks() -> None:
    """A low-valence turn must set an expiry N game ticks ahead, not N seconds ahead."""
    clock = GameClock(mode="game_driven")
    await clock.advance(tick_delta=100, time_delta_seconds=0)
    repo = _make_repo()
    handler = _make_handler(
        clock=clock,
        emotion_updater=_RecordingEmotionUpdater(valence=-99),
        repo=repo,
    )

    await handler.handle(_request())

    kwargs = repo.set_routine_override.await_args.kwargs
    assert kwargs["expires_at_tick"] == 100 + LOW_VALENCE_ROUTINE_OVERRIDE_TICKS
