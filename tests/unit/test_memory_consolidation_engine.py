"""
test_memory_consolidation_engine.py - Unit tests for MemoryConsolidationEngine.

Does NOT: connect to Neo4j. All graph calls go through a mocked
MemoryConsolidationGraphPort and the LLM is mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.dialogue.session_store import SessionStore
from npc_engine.world.time_utils import TimePoint

_MCE_MODULE = "npc_engine.engines.memory_consolidation.memory_consolidation_engine"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(memory_id: str | None = "mem-uuid-001") -> MagicMock:
    """Return a MagicMock MemoryConsolidationGraphPort with async methods stubbed."""
    repo = MagicMock()
    repo.get_beliefs = AsyncMock(return_value=[])
    repo.get_recent_memories = AsyncMock(return_value=[])
    repo.get_undisclosed_witnesses = AsyncMock(return_value=[])
    repo.create_memory = AsyncMock(return_value=memory_id)
    return repo


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


def _make_settings(max_concurrent: int = 5) -> MagicMock:
    """Return a MagicMock Settings with MAX_CONCURRENT_TICKS set."""
    settings = MagicMock()
    settings.MAX_CONCURRENT_TICKS = max_concurrent
    return settings


# ---------------------------------------------------------------------------
# Engine construction — prompt loading is mocked to avoid real file I/O
# ---------------------------------------------------------------------------


def _make_engine(
    store: SessionStore,
    llm: MagicMock,
    threshold: int = 5,
    clear: bool = False,
    memory_repo: MagicMock | None = None,
    settings: MagicMock | None = None,
):
    """Return a MemoryConsolidationEngine with the prompt YAML mocked."""
    with patch(
        f"{_MCE_MODULE}.load_yaml_mapping",
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
            memory_repo=memory_repo or _make_repo(),
            settings=settings or _make_settings(),
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
    repo = _make_repo(memory_id="mem-uuid-001")
    engine = _make_engine(store, llm, threshold=5, memory_repo=repo)

    result = await engine.consolidate(npc_id=npc_id, game_time=_make_game_time())

    assert result == "mem-uuid-001"
    repo.create_memory.assert_awaited_once()
    call_kwargs = repo.create_memory.call_args.kwargs
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
    repo = _make_repo()
    engine = _make_engine(store, llm, threshold=5, memory_repo=repo)

    result = await engine.consolidate(npc_id=npc_id, game_time=_make_game_time())

    assert result is None
    llm.generate.assert_not_awaited()
    repo.create_memory.assert_not_awaited()


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
    repo = _make_repo()
    engine = _make_engine(store, llm, threshold=5, memory_repo=repo)

    result = await engine.consolidate(npc_id=npc_id, game_time=_make_game_time())

    assert result is None
    repo.create_memory.assert_not_awaited()


# ---------------------------------------------------------------------------
# clear_turns_after=True: session turns are cleared on success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consolidate_clears_turns_when_configured():
    npc_id = "npc_merchant"
    turns = [f"Turn {i}" for i in range(10)]
    store = await _make_store_with_turns(npc_id, turns)
    llm = _make_llm("The merchant remembered the trade.")
    engine = _make_engine(store, llm, threshold=5, clear=True, memory_repo=_make_repo("mem-uuid-002"))

    await engine.consolidate(npc_id=npc_id, game_time=_make_game_time())

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
    repo = _make_repo()
    repo.create_memory = AsyncMock(side_effect=lambda *, character_id, **kwargs: f"mem-{character_id}")
    engine = _make_engine(store, llm, threshold=5, memory_repo=repo)

    result = await engine.run_tick(game_time=_make_game_time())

    assert set(result["consolidated"]) == {"npc_a", "npc_b"}
    assert "npc_c" not in result["consolidated"]
    assert repo.create_memory.await_count == 2


# ---------------------------------------------------------------------------
# run_tick: scheduler's positional session kwarg is accepted and ignored (SEV-24)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_no_session_required():
    """run_tick accepts no session kwarg (SEV-24 Wave 5 — session coupling removed)."""
    store = SessionStore(ttl_seconds=300, max_turns=100)
    await store.append_turns("player1", "npc_a", [f"Turn {i}" for i in range(10)])

    repo = _make_repo()
    repo.create_memory = AsyncMock(side_effect=lambda *, character_id, **kwargs: f"mem-{character_id}")
    engine = _make_engine(store, _make_llm("Summary."), threshold=5, memory_repo=repo)

    result = await engine.run_tick(game_time=_make_game_time())

    assert result["consolidated"] == ["npc_a"]
