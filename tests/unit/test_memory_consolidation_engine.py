"""
test_memory_consolidation_engine.py - Unit tests for MemoryConsolidationEngine.

Does NOT: connect to Neo4j. All graph and LLM calls are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.dialogue.session_store import SessionStore
from npc_engine.world.time_utils import TimePoint

_MCE_MODULE = "npc_engine.engines.memory_consolidation.memory_consolidation_engine"


@pytest.fixture(autouse=True)
def _patch_context_graph_calls():
    """Patch the two context-enrichment graph calls added in 8.6 to return empty lists.
    These calls hit Neo4j and are irrelevant to the consolidation logic under test."""
    with (
        patch(f"{_MCE_MODULE}.get_beliefs_for_character", new_callable=AsyncMock, return_value=[]),
        patch(f"{_MCE_MODULE}.get_memories_for_character", new_callable=AsyncMock, return_value=[]),
    ):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> MagicMock:
    """Return a MagicMock behaving like an AsyncSession with a transaction."""
    session = MagicMock()
    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    session.begin_transaction = AsyncMock(return_value=tx)
    return session


def _make_game_time() -> TimePoint:
    return TimePoint(year=1, season="spring", day=5, time_of_day="afternoon")


async def _make_store_with_turns(npc_id: str, turns: list[str]) -> SessionStore:
    store = SessionStore(ttl_seconds=300, max_turns=100)
    await store.append_turns(player_id="player1", npc_id=npc_id, new_turns=turns)
    return store


def _make_llm(summary: str = "A memorable conversation happened.") -> MagicMock:
    llm = MagicMock()
    llm.generate = AsyncMock(return_value=summary)
    return llm


# ---------------------------------------------------------------------------
# Engine construction — prompt loading is mocked to avoid real file I/O
# ---------------------------------------------------------------------------


def _make_engine(store: SessionStore, llm: MagicMock, threshold: int = 5, clear: bool = False):
    """Return a MemoryConsolidationEngine with the prompt YAML mocked."""
    with patch(
        "npc_engine.engines.memory_consolidation.memory_consolidation_engine.load_yaml_mapping",
        return_value={
            "system": "You are an archivist.",
            "user_template": "NPC_ID: {npc_id}\nTURNS:\n{turns_text}",
        },
    ):
        from npc_engine.engines.memory_consolidation.memory_consolidation_engine import (
            MemoryConsolidationEngine,
        )

        return MemoryConsolidationEngine(
            session_store=store,
            llm_client=llm,
            turn_threshold=threshold,
            clear_turns_after=clear,
        )


# ---------------------------------------------------------------------------
# Happy path: enough turns → LLM called → memory created
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consolidate_enough_turns_creates_memory():
    npc_id = "npc_inn"
    turns = [f"Turn {i}" for i in range(10)]
    store = await _make_store_with_turns(npc_id, turns)
    llm = _make_llm("We talked about the festival.")
    engine = _make_engine(store, llm, threshold=5)
    session = _make_session()

    with patch(
        "npc_engine.engines.memory_consolidation.memory_consolidation_engine.create_memory",
        new_callable=AsyncMock,
        return_value="mem-uuid-001",
    ) as mock_create:
        result = await engine.consolidate(session, npc_id=npc_id, game_time=_make_game_time())

    assert result == "mem-uuid-001"
    mock_create.assert_awaited_once()
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["character_id"] == npc_id
    assert call_kwargs["vividness"] == 75
    assert call_kwargs["emotional_charge"] == 0
    llm.generate.assert_awaited_once()


# ---------------------------------------------------------------------------
# Skip path: fewer turns than threshold → None, no LLM call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consolidate_below_threshold_returns_none():
    npc_id = "npc_blacksmith"
    store = await _make_store_with_turns(npc_id, ["Hello", "Goodbye"])  # 2 turns < threshold 5
    llm = _make_llm()
    engine = _make_engine(store, llm, threshold=5)
    session = _make_session()

    with patch(
        "npc_engine.engines.memory_consolidation.memory_consolidation_engine.create_memory",
        new_callable=AsyncMock,
    ) as mock_create:
        result = await engine.consolidate(session, npc_id=npc_id, game_time=_make_game_time())

    assert result is None
    llm.generate.assert_not_awaited()
    mock_create.assert_not_awaited()


# ---------------------------------------------------------------------------
# LLM failure: graceful skip — no crash, returns None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consolidate_llm_failure_returns_none_without_crash():
    npc_id = "npc_guard"
    turns = [f"Turn {i}" for i in range(10)]
    store = await _make_store_with_turns(npc_id, turns)
    llm = MagicMock()
    llm.generate = AsyncMock(side_effect=RuntimeError("LLM timed out"))
    engine = _make_engine(store, llm, threshold=5)
    session = _make_session()

    with patch(
        "npc_engine.engines.memory_consolidation.memory_consolidation_engine.create_memory",
        new_callable=AsyncMock,
    ) as mock_create:
        result = await engine.consolidate(session, npc_id=npc_id, game_time=_make_game_time())

    assert result is None
    mock_create.assert_not_awaited()


# ---------------------------------------------------------------------------
# clear_turns_after=True: session turns are cleared on success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consolidate_clears_turns_when_configured():
    npc_id = "npc_merchant"
    turns = [f"Turn {i}" for i in range(10)]
    store = await _make_store_with_turns(npc_id, turns)
    llm = _make_llm("The merchant remembered the trade.")
    engine = _make_engine(store, llm, threshold=5, clear=True)
    session = _make_session()

    with patch(
        "npc_engine.engines.memory_consolidation.memory_consolidation_engine.create_memory",
        new_callable=AsyncMock,
        return_value="mem-uuid-002",
    ):
        await engine.consolidate(session, npc_id=npc_id, game_time=_make_game_time())

    assert await store.get_all_turns_for_npc(npc_id) == []


# ---------------------------------------------------------------------------
# run_tick: consolidates all eligible NPCs and returns ids
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_consolidates_all_eligible_npcs():
    store = SessionStore(ttl_seconds=300, max_turns=100)
    await store.append_turns("player1", "npc_a", [f"Turn {i}" for i in range(10)])
    await store.append_turns("player1", "npc_b", [f"Turn {i}" for i in range(10)])
    await store.append_turns("player1", "npc_c", ["Only one turn"])  # below threshold

    llm = _make_llm("Summary.")
    engine = _make_engine(store, llm, threshold=5)
    session = _make_session()
    game_time = _make_game_time()

    call_count = 0

    async def _fake_create(sess, *, character_id, **kwargs):
        nonlocal call_count
        call_count += 1
        return f"mem-{character_id}"

    with patch(
        "npc_engine.engines.memory_consolidation.memory_consolidation_engine.create_memory",
        new=_fake_create,
    ):
        result = await engine.run_tick(session, game_time=game_time)

    assert set(result["consolidated"]) == {"npc_a", "npc_b"}
    assert "npc_c" not in result["consolidated"]
    assert call_count == 2
