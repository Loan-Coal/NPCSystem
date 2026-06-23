"""Unit tests for Neo4jPoliticalRepository (DEC-122 / SEV-24 graph repository seam)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.political_repository import Neo4jPoliticalRepository

_MOD = "npc_engine.graph.repositories.political_repository"


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
async def test_get_vacant_titles_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jPoliticalRepository(db)  # type: ignore[arg-type]
    titles = [{"id": "t1", "faction_id": "f1"}]

    with patch(f"{_MOD}.get_vacant_inheritable_titles", new=AsyncMock(return_value=titles)) as mock_fn:
        result = await repo.get_vacant_inheritable_titles()

    assert result == titles
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_get_heirs_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jPoliticalRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.get_heirs_for_character", new=AsyncMock(return_value=[])) as mock_fn:
        await repo.get_heirs_for_character(character_id="c1")

    mock_fn.assert_awaited_once_with(session, character_id="c1")


@pytest.mark.asyncio
async def test_grant_title_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jPoliticalRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.grant_title", new=AsyncMock()) as mock_fn:
        await repo.grant_title(character_id="c1", title_id="t1", tick=7)

    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session, character_id="c1", title_id="t1", tick=7)
