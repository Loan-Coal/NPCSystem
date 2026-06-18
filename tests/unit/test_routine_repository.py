"""Unit tests for Neo4jRoutineRepository (DEC-122 / SEV-24 graph repository seam)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.routine_repository import Neo4jRoutineRepository

_MOD = "npc_engine.graph.repositories.routine_repository"


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
async def test_get_scheduled_characters_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jRoutineRepository(db)  # type: ignore[arg-type]
    rows = [{"character_id": "c1"}]

    with patch(f"{_MOD}.get_scheduled_characters", new=AsyncMock(return_value=rows)) as mock_fn:
        result = await repo.get_scheduled_characters()

    assert result == rows
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session=session)


@pytest.mark.asyncio
async def test_update_character_location_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jRoutineRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.update_character_location", new=AsyncMock()) as mock_fn:
        await repo.update_character_location(character_id="c1", location_id="L", arrived_at_tick=5)

    mock_fn.assert_awaited_once_with(
        session=session, character_id="c1", location_id="L", arrived_at_tick=5
    )


@pytest.mark.asyncio
async def test_record_departure_delegates_positional_session():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jRoutineRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.record_departure", new=AsyncMock()) as mock_fn:
        await repo.record_departure(
            character_id="c1", location_id="L", arrived_at_tick=3, departed_at_tick=9, reason="routine"
        )

    mock_fn.assert_awaited_once_with(
        session, character_id="c1", location_id="L", arrived_at_tick=3, departed_at_tick=9, reason="routine"
    )
