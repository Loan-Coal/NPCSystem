"""Unit tests for Neo4jMemoryConsolidationRepository (DEC-122 / SEV-24 graph repository seam)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.memory_consolidation_repository import (
    Neo4jMemoryConsolidationRepository,
)
from npc_engine.world.time_utils import TimePoint

_MOD = "npc_engine.graph.repositories.memory_consolidation_repository"


class _FakeGraphDB:
    def __init__(self, session: Any) -> None:
        self._session = session
        self.connect_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[Any]:
        yield self._session


@pytest.mark.asyncio
async def test_get_beliefs_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMemoryConsolidationRepository(db)  # type: ignore[arg-type]
    rows = [{"content": "b"}]

    with patch(f"{_MOD}.get_beliefs_for_character", new=AsyncMock(return_value=rows)) as mock_fn:
        result = await repo.get_beliefs(character_id="npc1", k=5)

    assert result == rows
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session, character_id="npc1", k=5)


@pytest.mark.asyncio
async def test_get_recent_memories_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMemoryConsolidationRepository(db)  # type: ignore[arg-type]
    rows = [{"content": "m"}]

    with patch(f"{_MOD}.get_memories_for_character", new=AsyncMock(return_value=rows)) as mock_fn:
        result = await repo.get_recent_memories(character_id="npc1", k=3)

    assert result == rows
    mock_fn.assert_awaited_once_with(session, character_id="npc1", k=3)


@pytest.mark.asyncio
async def test_get_undisclosed_witnesses_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMemoryConsolidationRepository(db)  # type: ignore[arg-type]
    rows = [{"clarity": 90}]

    with patch(f"{_MOD}.get_undisclosed_witnesses", new=AsyncMock(return_value=rows)) as mock_fn:
        result = await repo.get_undisclosed_witnesses(npc_id="npc1")

    assert result == rows
    mock_fn.assert_awaited_once_with(session, npc_id="npc1")


@pytest.mark.asyncio
async def test_create_memory_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMemoryConsolidationRepository(db)  # type: ignore[arg-type]
    game_time = TimePoint(year=1, season="spring", day=5, time_of_day="afternoon")

    with patch(f"{_MOD}.create_memory", new=AsyncMock(return_value="mem-1")) as mock_fn:
        result = await repo.create_memory(
            character_id="npc1", content="summary", vividness=75, emotional_charge=0, game_time=game_time
        )

    assert result == "mem-1"
    mock_fn.assert_awaited_once_with(
        session,
        character_id="npc1",
        content="summary",
        vividness=75,
        emotional_charge=0,
        game_time=game_time,
    )
