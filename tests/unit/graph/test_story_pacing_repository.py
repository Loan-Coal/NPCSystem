"""Unit tests for Neo4jStoryPacingRepository (DEC-122 / SEV-24 graph repo seam)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.story_pacing_repository import Neo4jStoryPacingRepository

_MOD = "npc_engine.graph.repositories.story_pacing_repository"


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
async def test_get_active_high_severity_quests_delegates_positional():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jStoryPacingRepository(db)  # type: ignore[arg-type]
    rows = [{"quest_id": "q1", "severity": 80}]

    with patch(f"{_MOD}.get_active_high_severity_quests", new=AsyncMock(return_value=rows)) as mock_fn:
        result = await repo.get_active_high_severity_quests(threshold=70)

    assert result == rows
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session, 70)


@pytest.mark.asyncio
async def test_get_recent_major_events_delegates_positional():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jStoryPacingRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.get_recent_major_events", new=AsyncMock(return_value=[])) as mock_fn:
        await repo.get_recent_major_events(min_tick_id=5, floor=60)

    mock_fn.assert_awaited_once_with(session, 5, 60)
