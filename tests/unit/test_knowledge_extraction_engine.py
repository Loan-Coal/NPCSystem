"""
test_knowledge_extraction_engine.py - Unit tests for KnowledgeExtractionEngine.

Covers:
- process(): writes a belief for each valid fact.
- process(): skips facts that are too short (< 5 chars) or empty.
- process(): skips facts that are too long (> 300 chars).
- process(): returns correct written/skipped counts.
- write_belief(): calls session.run with the correct Cypher parameters.
- DialogueHandler: calls engine when KNOWLEDGE_LEARNING_ENABLED=True.
- DialogueHandler: skips engine call when KNOWLEDGE_LEARNING_ENABLED=False.
- DialogueHandler: does not raise AttributeError when knowledge_engine=None.
- process(): does NOT write a belief when find_conflicting_belief returns a match (dedup).
- process(): DOES write a belief when find_conflicting_belief returns None (no conflict).

Does NOT: connect to Neo4j, call an LLM, or read from disk.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("neo4j")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FALLBACK_PATH = str(_REPO_ROOT / "src" / "npc_engine" / "data" / "fallback_responses.json")
_CANNED_DIR = str(_REPO_ROOT / "prompts" / "canned")


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# KnowledgeExtractionEngine.process — core behaviour
# ---------------------------------------------------------------------------


def _make_repo(*, conflict: dict[str, Any] | None = None) -> AsyncMock:
    """Return a mock KnowledgeGraphPort with find_conflicting_belief/write_belief."""
    repo = AsyncMock()
    repo.find_conflicting_belief = AsyncMock(return_value=conflict)
    repo.write_belief = AsyncMock(return_value="belief-id")
    return repo


@pytest.mark.asyncio
async def test_writes_belief_for_each_fact():
    """Two valid facts should cause write_belief to be called exactly twice."""
    from npc_engine.engines.knowledge_learning.knowledge_extraction_engine import (
        KnowledgeExtractionEngine,
    )

    repo = _make_repo()
    engine = KnowledgeExtractionEngine(knowledge_repo=repo)
    await engine.process(
        npc_id="mira_innkeeper",
        player_id="player_1",
        tick=42,
        learned_facts=["I am the new captain", "the bandits moved to the old mill"],
        game_time_str="Year 1 Spring Day 1 Morning",
    )

    assert repo.write_belief.await_count == 2


@pytest.mark.asyncio
async def test_skips_empty_or_too_short_facts():
    """Empty string and strings shorter than 5 chars should be skipped."""
    from npc_engine.engines.knowledge_learning.knowledge_extraction_engine import (
        KnowledgeExtractionEngine,
    )

    repo = _make_repo()
    engine = KnowledgeExtractionEngine(knowledge_repo=repo)
    result = await engine.process(
        npc_id="mira_innkeeper",
        player_id="player_1",
        tick=1,
        learned_facts=["", "ab", "xy"],
        game_time_str="Year 1 Spring Day 1 Morning",
    )

    repo.write_belief.assert_not_awaited()
    assert result.written == 0
    assert result.skipped == 3


@pytest.mark.asyncio
async def test_skips_too_long_facts():
    """Facts longer than 300 characters should be skipped."""
    from npc_engine.engines.knowledge_learning.knowledge_extraction_engine import (
        KnowledgeExtractionEngine,
    )

    too_long = "x" * 301
    repo = _make_repo()
    engine = KnowledgeExtractionEngine(knowledge_repo=repo)
    result = await engine.process(
        npc_id="mira_innkeeper",
        player_id="player_1",
        tick=1,
        learned_facts=[too_long],
        game_time_str="Year 1 Spring Day 1 Morning",
    )

    repo.write_belief.assert_not_awaited()
    assert result.written == 0
    assert result.skipped == 1


@pytest.mark.asyncio
async def test_returns_correct_written_count():
    """Three valid facts should produce result.written == 3."""
    from npc_engine.engines.knowledge_learning.knowledge_extraction_engine import (
        KnowledgeExtractionEngine,
    )

    facts = ["I hail from the north", "I carry a royal seal", "I seek the hidden vault"]
    repo = _make_repo()
    engine = KnowledgeExtractionEngine(knowledge_repo=repo)
    result = await engine.process(
        npc_id="mira_innkeeper",
        player_id="player_1",
        tick=5,
        learned_facts=facts,
        game_time_str="Year 1 Spring Day 1 Morning",
    )

    assert result.written == 3
    assert result.skipped == 0


@pytest.mark.asyncio
async def test_mixed_valid_and_invalid_facts():
    """Mix of valid and invalid facts: only valid ones written."""
    from npc_engine.engines.knowledge_learning.knowledge_extraction_engine import (
        KnowledgeExtractionEngine,
    )

    too_long = "y" * 301
    repo = _make_repo()
    engine = KnowledgeExtractionEngine(knowledge_repo=repo)
    result = await engine.process(
        npc_id="mira_innkeeper",
        player_id="player_1",
        tick=3,
        learned_facts=["ok fact here", "", too_long, "another valid fact"],
        game_time_str="Year 1 Spring Day 1 Morning",
    )

    assert repo.write_belief.await_count == 2
    assert result.written == 2
    assert result.skipped == 2


# ---------------------------------------------------------------------------
# knowledge_writer.write_belief — unit test with mocked session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_knowledge_writer_merges_belief_node():
    """write_belief must call tx.run with correct Cypher params."""
    from npc_engine.graph.knowledge_writer import write_belief

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.begin_transaction = AsyncMock(return_value=tx)

    belief_id = await write_belief(
        session,
        npc_id="mira_innkeeper",
        content="the north road is blocked",
        confidence=70,
        source_character_id="player_1",
        learned_at_tick=10,
        game_time_str="Year 1 Spring Day 2 Evening",
    )

    assert isinstance(belief_id, str) and len(belief_id) > 0
    tx.run.assert_awaited_once()
    call_kwargs = tx.run.call_args
    # Verify params passed to the Cypher include the key facts
    params = call_kwargs.kwargs if call_kwargs.kwargs else {}
    if not params and call_kwargs.args:
        # Some callers pass params as positional kwargs after the query
        params = call_kwargs.args[1] if len(call_kwargs.args) > 1 else {}
    assert params.get("content") == "the north road is blocked" or any(
        "the north road is blocked" in str(a) for a in call_kwargs.args
    )


# ---------------------------------------------------------------------------
# DialogueHandler integration: engine call gating
# ---------------------------------------------------------------------------


class _MinimalLLMClient:
    """Minimal fake LLM client for constructing a DialogueHandler in tests."""

    async def generate(self, prompt: str, max_tokens: int, temperature: float, **_: Any) -> str:
        return "ok"

    async def generate_structured(self, prompt: str, schema: dict[str, Any], max_tokens: int, **_: Any) -> dict[str, Any]:
        return {
            "npc_response": "I hear you.",
            "action": {"type": "speak"},
            "relation_deltas": {"trust": 0, "fear": 0, "affection": 0},
            "learned_facts": ["I am the new captain"],
        }

    async def stream(self, prompt: str, max_tokens: int, temperature: float, **_: Any) -> AsyncIterator[str]:
        if False:
            yield ""

    def model_name(self) -> str:
        return "mock"


class _FakeEmotionUpdater:
    async def get_state(self, npc_id: str) -> Any:
        return SimpleNamespace(label="neutral", arousal=10, valence=0)

    async def apply_dialogue_mood(self, npc_id: str, mood_update: str | None, session=None, tick: int = 0) -> Any:
        return SimpleNamespace(label=mood_update or "neutral", arousal=10, valence=0)


def _make_engine_model_config():  # type: ignore[return]
    from npc_engine.engines.llm_config_models import (
        EngineFallbackPolicy,
        EngineModelConfig,
        EngineModelParams,
        EnginePromptRef,
        EngineTimeoutsMs,
    )

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
        fallback=EngineFallbackPolicy(
            policy="graceful_degradation", tiers=["full", "graph_only", "canned"]
        ),
        timeouts_ms=EngineTimeoutsMs(full=30000, graph_only=10000, canned=100),
    )


def _make_handler(knowledge_engine=None, knowledge_learning_enabled: bool = False):
    from npc_engine.engines.dialogue.dialogue_handler import DialogueHandler
    from npc_engine.engines.dialogue.session_store import SessionStore
    from npc_engine.services.input_moderation import build_input_moderation_service
    from npc_engine.services.output_moderation import build_output_moderation_service

    settings = SimpleNamespace(
        LLM_FALLBACK_PATH=_FALLBACK_PATH,
        CANNED_RESPONSES_DIR=_CANNED_DIR,
        LOG_LLM_PROMPTS=False,
        ENV="dev",
        TTS_ENABLED=False,
        WORLD_ID="world",
        KNOWLEDGE_LEARNING_ENABLED=knowledge_learning_enabled,
    )

    world_state = SimpleNamespace(year=1, season="spring", day=1, time_of_day="morning")
    dialogue_repo = AsyncMock()
    dialogue_repo.get_npc_archetype = AsyncMock(return_value=None)
    dialogue_repo.get_npc_voice_descriptor = AsyncMock(return_value=None)
    dialogue_repo.get_world_state = AsyncMock(return_value=world_state)
    dialogue_repo.apply_relation_deltas = AsyncMock(return_value=None)
    dialogue_repo.set_routine_override = AsyncMock(return_value=None)
    dialogue_context = AsyncMock()
    dialogue_context.build_context = AsyncMock(return_value=("{}", []))
    return DialogueHandler(
        settings=settings,
        llm_client=_MinimalLLMClient(),
        llm_config=SimpleNamespace(),
        engine_model_config=_make_engine_model_config(),
        session_store=SessionStore(ttl_seconds=300, max_turns=10),
        emotion_updater=_FakeEmotionUpdater(),
        input_moderation=build_input_moderation_service("mature"),
        output_moderation=build_output_moderation_service("mature"),
        dialogue_repo=dialogue_repo,
        dialogue_context=dialogue_context,
        knowledge_engine=knowledge_engine,
    )


@pytest.mark.asyncio
async def test_handler_calls_engine_when_enabled(monkeypatch):
    """knowledge_engine.process must be called once when KNOWLEDGE_LEARNING_ENABLED=True."""
    from npc_engine.api.schemas import DialogueRequest

    mock_knowledge_engine = AsyncMock()
    from npc_engine.engines.knowledge_learning.models import KnowledgeExtractionResult

    mock_knowledge_engine.process = AsyncMock(
        return_value=KnowledgeExtractionResult(written=1, skipped=0)
    )

    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.build_dialogue_prompt",
        lambda request, serialized_context: "prompt",
    )
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.apply_phase_transition",
        AsyncMock(return_value=None),
    )

    handler = _make_handler(
        knowledge_engine=mock_knowledge_engine, knowledge_learning_enabled=True
    )
    handler._llm.generate_response = AsyncMock(
        return_value={
            "npc_response": "Indeed, captain.",
            "action": {"type": "speak"},
            "relation_deltas": {"trust": 1, "fear": 0, "affection": 0},
            "learned_facts": ["I am the new captain"],
        }
    )

    await handler.handle(
        DialogueRequest(
            player_id="player_1",
            npc_id="mira_innkeeper",
            player_message="I am the new captain",
            location_id="tavern",
        )
    )

    mock_knowledge_engine.process.assert_awaited_once()


@pytest.mark.asyncio
async def test_handler_skips_engine_when_disabled(monkeypatch):
    """knowledge_engine.process must NOT be called when KNOWLEDGE_LEARNING_ENABLED=False."""
    from npc_engine.api.schemas import DialogueRequest

    mock_knowledge_engine = AsyncMock()
    mock_knowledge_engine.process = AsyncMock()

    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.build_dialogue_prompt",
        lambda request, serialized_context: "prompt",
    )
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.apply_phase_transition",
        AsyncMock(return_value=None),
    )

    handler = _make_handler(
        knowledge_engine=mock_knowledge_engine, knowledge_learning_enabled=False
    )
    handler._llm.generate_response = AsyncMock(
        return_value={
            "npc_response": "Interesting.",
            "action": {"type": "speak"},
            "relation_deltas": {"trust": 0, "fear": 0, "affection": 0},
            "learned_facts": ["I am the new captain"],
        }
    )

    await handler.handle(
        DialogueRequest(
            player_id="player_1",
            npc_id="mira_innkeeper",
            player_message="I am the new captain",
            location_id="tavern",
        )
    )

    mock_knowledge_engine.process.assert_not_awaited()


@pytest.mark.asyncio
async def test_handler_skips_when_engine_none(monkeypatch):
    """No AttributeError should occur when knowledge_engine=None."""
    from npc_engine.api.schemas import DialogueRequest

    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.build_dialogue_prompt",
        lambda request, serialized_context: "prompt",
    )
    monkeypatch.setattr(
        "npc_engine.engines.dialogue.dialogue_handler.apply_phase_transition",
        AsyncMock(return_value=None),
    )

    handler = _make_handler(knowledge_engine=None, knowledge_learning_enabled=True)
    handler._llm.generate_response = AsyncMock(
        return_value={
            "npc_response": "Understood.",
            "action": {"type": "speak"},
            "relation_deltas": {"trust": 0, "fear": 0, "affection": 0},
            "learned_facts": ["I am the new captain"],
        }
    )

    # Must not raise
    await handler.handle(
        DialogueRequest(
            player_id="player_1",
            npc_id="mira_innkeeper",
            player_message="I am the new captain",
            location_id="tavern",
        )
    )


# ---------------------------------------------------------------------------
# EXP-215: Belief contradiction / dedup — pre-write check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_belief_is_not_rewritten():
    """When find_conflicting_belief returns a match, write_belief must NOT be called."""
    from npc_engine.engines.knowledge_learning.knowledge_extraction_engine import (
        KnowledgeExtractionEngine,
    )

    existing_belief = {"id": "b_existing", "content": "the north road is blocked", "confidence": 70}
    repo = _make_repo(conflict=existing_belief)
    engine = KnowledgeExtractionEngine(knowledge_repo=repo)
    result = await engine.process(
        npc_id="mira_innkeeper",
        player_id="player_1",
        tick=10,
        learned_facts=["the north road is blocked"],
        game_time_str="Year 1 Spring Day 2 Evening",
    )

    repo.write_belief.assert_not_awaited()
    assert result.written == 0
    assert result.skipped == 1


@pytest.mark.asyncio
async def test_non_conflicting_belief_is_written():
    """When find_conflicting_belief returns None, write_belief must be called once."""
    from npc_engine.engines.knowledge_learning.knowledge_extraction_engine import (
        KnowledgeExtractionEngine,
    )

    repo = _make_repo(conflict=None)
    engine = KnowledgeExtractionEngine(knowledge_repo=repo)
    result = await engine.process(
        npc_id="mira_innkeeper",
        player_id="player_1",
        tick=10,
        learned_facts=["the eastern gate is open"],
        game_time_str="Year 1 Spring Day 2 Evening",
    )

    repo.write_belief.assert_awaited_once()
    assert result.written == 1
    assert result.skipped == 0
