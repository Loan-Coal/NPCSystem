"""
test_dialogue_context_receipt.py - The context receipt on DialogueResponse (item B).

Does NOT: call live LLM services; open Neo4j sessions.

Dependencies injected: fake LLM client, mock Neo4jDialogueRepository, mock Neo4jDialogueContextAdapter.

What is under test is an attribution property, not a feature. Retrieval precision measured
over what the retriever RANKED and precision measured over what SURVIVED the prompt budget
are different numbers, and only the first is observable without this receipt. A response
that carries a profile label but not the items that reached the model would let an arm be
scored against context it never saw.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FALLBACK_PATH = str(_REPO_ROOT / "src" / "npc_engine" / "data" / "fallback_responses.json")
_CANNED_DIR = str(_REPO_ROOT / "prompts" / "canned")

from npc_engine.api.schemas import DialogueRequest, DialogueResponse
from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler
from npc_engine.engines.dialogue.session_store import SessionStore
from npc_engine.engines.llm_config_models import (
    EngineFallbackPolicy,
    EngineModelConfig,
    EngineModelParams,
    EnginePromptRef,
    EngineTimeoutsMs,
)
from npc_engine.retrieval.context.context_receipt import ContextReceipt
from npc_engine.scheduler.game_clock import GameClock
from npc_engine.services.input_moderation import build_input_moderation_service
from npc_engine.services.output_moderation import build_output_moderation_service


_RECEIPT = ContextReceipt(
    retrieval_profile="aggressive",
    item_keys=("character:npc_1", "world_state"),
    dropped_keys=("rag:r1",),
    total_tokens=123,
    prompt_token_budget=512,
    budget_trimmed=True,
)


def _engine_model_config() -> EngineModelConfig:
    return EngineModelConfig(
        engine="dialogue",
        llm=EngineModelParams(
            backend="mock", model="mock", temperature=0.7, max_tokens=512, top_p=0.95,
            stop_sequences=[],
        ),
        prompt=EnginePromptRef(name="dialogue_main", version="v1"),
        output_schema_ref="dialogue_response_v1",
        fallback=EngineFallbackPolicy(
            policy="graceful_degradation", tiers=["full", "graph_only", "canned"],
        ),
        timeouts_ms=EngineTimeoutsMs(full=30000, graph_only=10000, canned=100),
    )


class _MinimalLLMClient:
    """Fake client returning a valid structured dialogue payload."""

    async def generate(self, prompt: str, max_tokens: int, temperature: float, top_p=None,
                       stop_sequences=None, system=None, seed=None) -> str:
        return "ok"

    async def generate_structured(self, prompt: str, schema: dict[str, Any], max_tokens: int,
                                  top_p=None, stop_sequences=None, system=None,
                                  seed=None) -> dict[str, Any]:
        return {"npc_response": "Well met."}

    async def stream(self, prompt: str, max_tokens: int, temperature: float, top_p=None,
                     stop_sequences=None, system=None, seed=None) -> AsyncIterator[str]:
        if False:
            yield ""

    def model_name(self) -> str:
        return "mock"


class _FakeEmotionUpdater:
    """Deterministic emotion updater for handler construction."""

    async def get_state(self, npc_id: str):
        return SimpleNamespace(label="neutral")

    async def apply_dialogue_mood(self, npc_id: str, mood_update: str | None, tick: int = 0):
        return SimpleNamespace(label=mood_update or "neutral", valence=0)


def _make_handler(context_port: MagicMock) -> DialogueHandler:
    repo = AsyncMock()
    repo.get_npc_archetype = AsyncMock(return_value=None)
    repo.get_npc_voice_descriptor = AsyncMock(return_value=None)
    repo.get_world_state = AsyncMock(return_value=None)
    repo.apply_relation_deltas = AsyncMock(return_value=None)
    repo.set_routine_override = AsyncMock(return_value=None)
    return DialogueHandler(
        settings=SimpleNamespace(
            LLM_FALLBACK_PATH=_FALLBACK_PATH,
            CANNED_RESPONSES_DIR=_CANNED_DIR,
            LOG_LLM_PROMPTS=False,
        ),
        llm_client=_MinimalLLMClient(),
        llm_config=SimpleNamespace(),
        engine_model_config=_engine_model_config(),
        session_store=SessionStore(ttl_seconds=300, max_turns=10),
        emotion_updater=_FakeEmotionUpdater(),
        input_moderation=build_input_moderation_service("mature"),
        output_moderation=build_output_moderation_service("mature"),
        dialogue_repo=repo,
        dialogue_context=context_port,
        clock=GameClock(mode="game_driven"),
    )


def _context_port() -> MagicMock:
    port = AsyncMock()
    port.build_context = AsyncMock(return_value=("{}", [], _RECEIPT))
    return port


# ---------------------------------------------------------------------------
# The contract on the models
# ---------------------------------------------------------------------------


def test_response_carries_no_receipt_by_default() -> None:
    """Opt-in: an ordinary response must look exactly as it did before the field existed."""
    response = DialogueResponse(npc_response="hi")

    assert response.context_receipt is None
    assert "context_receipt" not in response.model_dump(exclude_none=True)


def test_request_does_not_ask_for_a_receipt_by_default() -> None:
    req = DialogueRequest(player_id="p1", npc_id="npc_1", player_message="hi")

    assert req.include_context_receipt is False


# ---------------------------------------------------------------------------
# The contract through the handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handler_attaches_the_receipt_when_the_request_asks_for_it() -> None:
    handler = _make_handler(_context_port())

    response = await handler.handle(DialogueRequest(
        player_id="p1", npc_id="npc_1", player_message="hello",
        session_id="s1", include_context_receipt=True,
    ))

    assert response.context_receipt is not None
    assert response.context_receipt.retrieval_profile == "aggressive"
    assert response.context_receipt.item_keys == ("character:npc_1", "world_state")
    assert response.context_receipt.budget_trimmed is True


@pytest.mark.asyncio
async def test_handler_withholds_the_receipt_when_the_request_does_not_ask() -> None:
    """The engine always builds one; exposing it is the caller's choice."""
    handler = _make_handler(_context_port())

    response = await handler.handle(DialogueRequest(
        player_id="p1", npc_id="npc_1", player_message="hello", session_id="s1",
    ))

    assert response.context_receipt is None


@pytest.mark.asyncio
async def test_a_legacy_cache_hit_yields_no_receipt_rather_than_a_fabricated_one() -> None:
    """A cached context has no assembly to report. None is the honest answer; an empty
    receipt would read as 'nothing reached the model', which is false."""
    port = AsyncMock()
    port.build_context = AsyncMock(return_value=("{}", [], None))
    handler = _make_handler(port)

    response = await handler.handle(DialogueRequest(
        player_id="p1", npc_id="npc_1", player_message="hello",
        session_id="s1", include_context_receipt=True,
    ))

    assert response.context_receipt is None


@pytest.mark.asyncio
async def test_asking_for_a_receipt_does_not_change_the_prompt(monkeypatch) -> None:
    """THE guard for B: the flag is a reporting switch, never an engine change.

    Regeneration #1 has not run yet and each labelled regeneration costs ~147 re-adjudicated
    human labels against a budget of 2, so a flag that perturbed the prompt would be far more
    expensive than the receipt is worth.
    """
    from npc_engine.engines.dialogue.prompt_builder import build_dialogue_prompt as _real

    prompts: list[str] = []

    def _spy(request, serialized_context):
        built = _real(request=request, serialized_context=serialized_context)
        prompts.append(built)
        return built

    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.build_dialogue_prompt", _spy,
    )
    for flag in (False, True):
        handler = _make_handler(_context_port())
        await handler.handle(DialogueRequest(
            player_id="p1", npc_id="npc_1", player_message="hello",
            session_id="s1", include_context_receipt=flag,
        ))

    assert len(prompts) == 2
    assert prompts[0] == prompts[1]


# ---------------------------------------------------------------------------
# The contract on the port
# ---------------------------------------------------------------------------


def test_adapter_build_context_return_carries_context_receipt() -> None:
    """SEV-15: Neo4jDialogueContextAdapter.build_context must declare ContextReceipt in its
    return type so callers get full attribution (receipt, not None) on a cache miss."""
    from npc_engine.retrieval.dialogue_context.dialogue_context_adapter import (
        Neo4jDialogueContextAdapter,
    )

    adapter_return = inspect.signature(Neo4jDialogueContextAdapter.build_context).return_annotation

    assert "ContextReceipt" in str(adapter_return)
