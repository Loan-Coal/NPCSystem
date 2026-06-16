"""
test_sev06_semaphore.py - Regression test for SEV-06 consolidation fan-out semaphore.

Verifies that run_tick() parallelises NPC consolidation up to MAX_CONCURRENT_TICKS
concurrent tasks, so wall-clock time scales as ceil(N / MAX_CONCURRENT_TICKS)*delay
rather than N*delay.

Does NOT: connect to Neo4j or any LLM. All I/O is mocked.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.dialogue.session_store import SessionStore
from npc_engine.world.time_utils import TimePoint

_MCE_MODULE = "npc_engine.engines.memory_consolidation.memory_consolidation_engine"

_NPC_COUNT = 40
_MAX_CONCURRENT = 5
_TASK_DELAY_S = 0.01  # 10 ms per NPC consolidation
# Expected wall time ≈ ceil(40 / 5) * 10ms = 80ms; allow 3× headroom for CI jitter
_SERIAL_LOWER_BOUND_S = _NPC_COUNT * _TASK_DELAY_S * 0.5  # 200ms — serial would exceed this
_PARALLEL_UPPER_BOUND_S = (_NPC_COUNT / _MAX_CONCURRENT + 1) * _TASK_DELAY_S * 3  # ~270ms


def _make_repo() -> MagicMock:
    """Return a MagicMock MemoryConsolidationGraphPort with empty-context reads stubbed."""
    repo = MagicMock()
    repo.get_beliefs = AsyncMock(return_value=[])
    repo.get_recent_memories = AsyncMock(return_value=[])
    repo.get_undisclosed_witnesses = AsyncMock(return_value=[])
    repo.create_memory = AsyncMock(return_value="mem-x")
    return repo


def _make_settings(max_concurrent: int = _MAX_CONCURRENT) -> MagicMock:
    settings = MagicMock()
    settings.MAX_CONCURRENT_TICKS = max_concurrent
    return settings


async def _make_store_with_npcs(npc_ids: list[str], turns_per_npc: int = 10) -> SessionStore:
    store = SessionStore(ttl_seconds=300, max_turns=200)
    for npc_id in npc_ids:
        # SEV-05 made SessionStore mutators async; the coroutine must be awaited.
        await store.append_turns("player1", npc_id, [f"Turn {i}" for i in range(turns_per_npc)])
    return store


def _make_engine(store: SessionStore, memory_repo: MagicMock, settings: MagicMock):
    """Build a MemoryConsolidationEngine with all file I/O mocked."""
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

        llm = MagicMock()
        llm.generate = AsyncMock(return_value="summary")
        return MemoryConsolidationEngine(
            session_store=store,
            llm_client=llm,
            memory_repo=memory_repo,
            settings=settings,
            turn_threshold=5,
        )


@pytest.mark.asyncio
async def test_run_tick_parallelises_up_to_max_concurrent_ticks():
    """Wall time must be << serial time, proving parallelism is capped by the semaphore."""
    npc_ids = [f"npc_{i:03d}" for i in range(_NPC_COUNT)]
    store = await _make_store_with_npcs(npc_ids)
    repo = _make_repo()
    settings = _make_settings(_MAX_CONCURRENT)
    engine = _make_engine(store, repo, settings)
    game_time = TimePoint(year=1, season="spring", day=1, time_of_day="morning")

    async def _slow_create(*, character_id, **kwargs):
        await asyncio.sleep(_TASK_DELAY_S)
        return f"mem-{character_id}"

    repo.create_memory = AsyncMock(side_effect=_slow_create)
    t0 = time.monotonic()
    result = await engine.run_tick(game_time=game_time)
    elapsed = time.monotonic() - t0

    assert len(result["consolidated"]) == _NPC_COUNT, (
        f"Expected {_NPC_COUNT} consolidated, got {len(result['consolidated'])}"
    )
    assert elapsed < _PARALLEL_UPPER_BOUND_S, (
        f"run_tick took {elapsed:.3f}s — expected < {_PARALLEL_UPPER_BOUND_S:.3f}s "
        f"(serial would be {_NPC_COUNT * _TASK_DELAY_S:.3f}s)"
    )
    assert elapsed < _SERIAL_LOWER_BOUND_S is False or elapsed < _PARALLEL_UPPER_BOUND_S, (
        "Timing assertion failure — check _PARALLEL_UPPER_BOUND_S constant"
    )


@pytest.mark.asyncio
async def test_run_tick_returns_only_successful_consolidations():
    """NPCs whose consolidate() returns None are excluded from the result."""
    all_npcs = [f"npc_{i}" for i in range(10)]
    # Only first 5 get enough turns
    store = SessionStore(ttl_seconds=300, max_turns=100)
    for npc_id in all_npcs[:5]:
        await store.append_turns("player1", npc_id, [f"Turn {i}" for i in range(10)])
    for npc_id in all_npcs[5:]:
        await store.append_turns("player1", npc_id, ["only one turn"])

    repo = _make_repo()
    settings = _make_settings()
    engine = _make_engine(store, repo, settings)
    game_time = TimePoint(year=1, season="spring", day=1, time_of_day="morning")

    async def _ok_create(*, character_id, **kwargs):
        return f"mem-{character_id}"

    repo.create_memory = AsyncMock(side_effect=_ok_create)
    result = await engine.run_tick(game_time=game_time)

    assert set(result["consolidated"]) == set(all_npcs[:5])
