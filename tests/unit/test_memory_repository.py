"""Unit tests for Neo4jMemoryRepository (DEC-122 / SEV-24 memory slice).

Covers the MemoryGraphPort adapter against a fake GraphDB (session-per-call seam):
each method opens one session and delegates to the matching memory_service function.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.memory_repository import Neo4jMemoryRepository
from npc_engine.world.time_utils import TimePoint

_MOD = "npc_engine.graph.repositories.memory_repository"


class _FakeGraphDB:
    def __init__(self, session: Any) -> None:
        self._session = session
        self.connect_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[Any]:
        yield self._session


def _game_time() -> TimePoint:
    return TimePoint(year=1, season="spring", day=1, time_of_day="morning")


@pytest.mark.asyncio
async def test_create_memory_delegates_keyword_args():
    db = _FakeGraphDB(object())
    repo = Neo4jMemoryRepository(db)  # type: ignore[arg-type]
    gt = _game_time()

    with patch(f"{_MOD}.create_memory", new=AsyncMock(return_value="mem-1")) as fn:
        result = await repo.create_memory(
            character_id="npc_1",
            content="A battle erupted",
            vividness=80,
            emotional_charge=30,
            game_time=gt,
            subject_player_id="player_hero",
            kind="episodic",
        )

    assert result == "mem-1"
    assert db.connect_calls == 1
    fn.assert_awaited_once_with(
        db._session,
        character_id="npc_1",
        content="A battle erupted",
        vividness=80,
        emotional_charge=30,
        game_time=gt,
        subject_player_id="player_hero",
        kind="episodic",
    )


@pytest.mark.asyncio
async def test_decay_all_vividness_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jMemoryRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.decay_all_vividness", new=AsyncMock(return_value=7)) as fn:
        result = await repo.decay_all_vividness()

    assert result == 7
    assert db.connect_calls == 1
    fn.assert_awaited_once_with(db._session)


@pytest.mark.asyncio
async def test_decay_all_vividness_weighted_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jMemoryRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.decay_all_vividness_weighted", new=AsyncMock(return_value=3)) as fn:
        result = await repo.decay_all_vividness_weighted(base_decay=5, charge_divisor=20)

    assert result == 3
    fn.assert_awaited_once_with(db._session, base_decay=5, charge_divisor=20)
