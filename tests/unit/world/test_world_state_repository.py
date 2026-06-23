"""Unit tests for Neo4jWorldStateRepository (DEC-122 / SEV-24 shared graph repo seam)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.world_state_repository import Neo4jWorldStateRepository
from npc_engine.world.world_state import WorldState

_MOD = "npc_engine.graph.repositories.world_state_repository"


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
async def test_get_world_state_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jWorldStateRepository(db)  # type: ignore[arg-type]
    ws = WorldState()

    with patch(f"{_MOD}.get_world_state", new=AsyncMock(return_value=ws)) as mock_fn:
        result = await repo.get_world_state(world_id="world")

    assert result is ws
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session, world_id="world")


@pytest.mark.asyncio
async def test_upsert_world_state_delegates_and_returns():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jWorldStateRepository(db)  # type: ignore[arg-type]
    ws = WorldState(max_event_severity=30)

    with patch(f"{_MOD}.upsert_world_state", new=AsyncMock(return_value=ws)) as mock_fn:
        result = await repo.upsert_world_state(world_state=ws)

    assert result is ws
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session, ws)
