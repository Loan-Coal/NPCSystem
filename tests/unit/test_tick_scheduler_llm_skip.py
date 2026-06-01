"""
test_tick_scheduler_llm_skip.py - Unit tests for skip_llm_engines flag and chapter_interval.

Does NOT: exercise real Neo4j or LLM calls.

Dependencies injected: FakeSession, FakeEngine stubs.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from npc_engine.scheduler.game_clock import GameClock
from npc_engine.scheduler.tick_scheduler import TickScheduler


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, row: dict[str, Any] | None):
        self._row = row

    async def single(self):
        return self._row

    async def consume(self) -> None:
        pass


class _FakeSession:
    async def run(self, query: str, **kwargs):
        if "WorldState" in query:
            return _FakeResult(None)
        return _FakeResult({"done": False})


class _FakeEngine:
    """Records run_tick calls."""

    def __init__(self) -> None:
        self.tick_ids: list[int] = []

    async def run_tick(self, session, tick_id: int, **kwargs) -> dict:
        self.tick_ids.append(tick_id)
        return {"tick_id": tick_id}


class _FakeMemoryEngine:
    """Records run_tick calls (uses game_time kwarg, not tick_id)."""

    def __init__(self) -> None:
        self.calls: int = 0

    async def run_tick(self, session, game_time, **kwargs) -> dict:
        self.calls += 1
        return {"consolidated": []}


def _make_scheduler(
    *,
    gossip_engine: _FakeEngine | None = None,
    event_engine: _FakeEngine | None = None,
    chapter_engine: _FakeEngine | None = None,
    memory_consolidation_engine: _FakeMemoryEngine | None = None,
    chapter_interval: int = 1,
    consolidation_advance_interval: int = 1,
) -> TickScheduler:
    clock = GameClock(mode="game_driven")
    gossip = gossip_engine or _FakeEngine()
    event = event_engine or _FakeEngine()
    return TickScheduler(
        clock=clock,
        gossip_handler=gossip,
        event_handler=event,
        gossip_interval=1,
        event_interval=1,
        chapter_engine=chapter_engine,
        memory_consolidation_engine=memory_consolidation_engine,
        chapter_interval=chapter_interval,
        consolidation_advance_interval=consolidation_advance_interval,
    )


# ---------------------------------------------------------------------------
# skip_llm_engines — chapter engine
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chapter_engine_runs_when_skip_llm_false() -> None:
    chapter = _FakeEngine()
    scheduler = _make_scheduler(chapter_engine=chapter)
    session = _FakeSession()
    await scheduler.advance(session=session, tick_delta=1, time_delta_seconds=0)
    assert chapter.tick_ids == [1]


@pytest.mark.asyncio
async def test_chapter_engine_skipped_when_skip_llm_true() -> None:
    chapter = _FakeEngine()
    scheduler = _make_scheduler(chapter_engine=chapter)
    session = _FakeSession()
    await scheduler.advance(session=session, tick_delta=1, time_delta_seconds=0, skip_llm_engines=True)
    assert chapter.tick_ids == []


@pytest.mark.asyncio
async def test_chapter_engine_skipped_resumes_next_advance() -> None:
    chapter = _FakeEngine()
    scheduler = _make_scheduler(chapter_engine=chapter)
    session = _FakeSession()
    await scheduler.advance(session=session, tick_delta=1, time_delta_seconds=0, skip_llm_engines=True)
    await scheduler.advance(session=session, tick_delta=1, time_delta_seconds=0, skip_llm_engines=False)
    assert chapter.tick_ids == [2]


# ---------------------------------------------------------------------------
# skip_llm_engines — memory_consolidation engine
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_memory_consolidation_runs_when_skip_llm_false() -> None:
    memory = _FakeMemoryEngine()
    scheduler = _make_scheduler(memory_consolidation_engine=memory, consolidation_advance_interval=1)
    session = _FakeSession()
    await scheduler.advance(session=session, tick_delta=1, time_delta_seconds=0)
    assert memory.calls == 1


@pytest.mark.asyncio
async def test_memory_consolidation_skipped_when_skip_llm_true() -> None:
    memory = _FakeMemoryEngine()
    scheduler = _make_scheduler(memory_consolidation_engine=memory, consolidation_advance_interval=1)
    session = _FakeSession()
    await scheduler.advance(session=session, tick_delta=1, time_delta_seconds=0, skip_llm_engines=True)
    assert memory.calls == 0


# ---------------------------------------------------------------------------
# chapter_interval cadence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chapter_runs_every_tick_when_interval_1() -> None:
    chapter = _FakeEngine()
    scheduler = _make_scheduler(chapter_engine=chapter, chapter_interval=1)
    session = _FakeSession()
    await scheduler.advance(session=session, tick_delta=3, time_delta_seconds=0)
    assert chapter.tick_ids == [1, 2, 3]


@pytest.mark.asyncio
async def test_chapter_skips_intermediate_ticks_when_interval_3() -> None:
    chapter = _FakeEngine()
    scheduler = _make_scheduler(chapter_engine=chapter, chapter_interval=3)
    session = _FakeSession()
    await scheduler.advance(session=session, tick_delta=6, time_delta_seconds=0)
    # Chapter runs on ticks divisible by 3: 3 and 6
    assert chapter.tick_ids == [3, 6]


@pytest.mark.asyncio
async def test_chapter_interval_clamped_to_1() -> None:
    chapter = _FakeEngine()
    scheduler = _make_scheduler(chapter_engine=chapter, chapter_interval=0)
    session = _FakeSession()
    await scheduler.advance(session=session, tick_delta=2, time_delta_seconds=0)
    # Interval clamped to 1 → runs every tick
    assert chapter.tick_ids == [1, 2]


# ---------------------------------------------------------------------------
# skip_llm + chapter_interval combined
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chapter_skipped_even_when_interval_due_and_skip_llm_true() -> None:
    chapter = _FakeEngine()
    scheduler = _make_scheduler(chapter_engine=chapter, chapter_interval=3)
    session = _FakeSession()
    # Advance to tick 3 (interval due) but with skip_llm_engines=True
    await scheduler.advance(session=session, tick_delta=3, time_delta_seconds=0, skip_llm_engines=True)
    assert chapter.tick_ids == []


# ---------------------------------------------------------------------------
# advance_count not incremented when skip_llm skips consolidation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_advance_count_still_increments_even_when_llm_skipped() -> None:
    memory = _FakeMemoryEngine()
    scheduler = _make_scheduler(memory_consolidation_engine=memory, consolidation_advance_interval=2)
    session = _FakeSession()
    # Skip first advance
    await scheduler.advance(session=session, tick_delta=1, time_delta_seconds=0, skip_llm_engines=True)
    # Second advance (count=2, interval=2) — LLM allowed this time
    await scheduler.advance(session=session, tick_delta=1, time_delta_seconds=0, skip_llm_engines=False)
    # advance_count is 2, 2 % 2 == 0 → consolidation runs
    assert memory.calls == 1
