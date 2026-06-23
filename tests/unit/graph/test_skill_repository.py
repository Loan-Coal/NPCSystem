"""Unit tests for Neo4jSkillRepository (DEC-122 / SEV-24 graph repository seam)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.skill_repository import Neo4jSkillRepository

_MOD = "npc_engine.graph.repositories.skill_repository"


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
async def test_get_completed_quests_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jSkillRepository(db)  # type: ignore[arg-type]
    rows = [{"character_id": "c1", "skill_id": "s1", "quest_id": "q1"}]

    with patch(f"{_MOD}.get_completed_quests_with_skills", new=AsyncMock(return_value=rows)) as mock_fn:
        result = await repo.get_completed_quests_with_skills(tick_id=5)

    assert result == rows
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session, tick_id=5)


@pytest.mark.asyncio
async def test_increment_xp_delegates_and_returns_level():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jSkillRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.increment_xp", new=AsyncMock(return_value=4)) as mock_fn:
        level = await repo.increment_xp(character_id="c1", skill_id="s1", xp_delta=50, tick=5)

    assert level == 4
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session, character_id="c1", skill_id="s1", xp_delta=50, tick=5)
