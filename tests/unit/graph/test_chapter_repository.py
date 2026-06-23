"""Unit tests for Neo4jChapterRepository (DEC-122 / SEV-24 graph repository seam)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.chapter_repository import Neo4jChapterRepository

_MOD = "npc_engine.graph.repositories.chapter_repository"


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
async def test_get_current_chapter_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jChapterRepository(db)  # type: ignore[arg-type]
    row = {"id": "ch_1"}

    with patch(f"{_MOD}.get_current_chapter", new=AsyncMock(return_value=row)) as mock_fn:
        result = await repo.get_current_chapter()

    assert result == row
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_count_completed_quests_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jChapterRepository(db)  # type: ignore[arg-type]

    with patch(
        f"{_MOD}.count_completed_quests_since_tick", new=AsyncMock(return_value=4)
    ) as mock_fn:
        result = await repo.count_completed_quests_since_tick(since_tick=10)

    assert result == 4
    mock_fn.assert_awaited_once_with(session, since_tick=10)


@pytest.mark.asyncio
async def test_get_recent_events_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jChapterRepository(db)  # type: ignore[arg-type]
    rows = [{"id": "e1"}]

    with patch(
        f"{_MOD}.get_recent_events_for_chapter", new=AsyncMock(return_value=rows)
    ) as mock_fn:
        result = await repo.get_recent_events_for_chapter(since_tick=5, limit=3)

    assert result == rows
    mock_fn.assert_awaited_once_with(session, since_tick=5, limit=3)


@pytest.mark.asyncio
async def test_get_faction_standings_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jChapterRepository(db)  # type: ignore[arg-type]
    rows = [{"name": "Crown", "power_score": 90}]

    with patch(
        f"{_MOD}.get_faction_standings_summary", new=AsyncMock(return_value=rows)
    ) as mock_fn:
        result = await repo.get_faction_standings_summary(limit=5)

    assert result == rows
    mock_fn.assert_awaited_once_with(session, limit=5)


@pytest.mark.asyncio
async def test_create_chapter_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jChapterRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.create_chapter", new=AsyncMock(return_value="ch_2")) as mock_fn:
        result = await repo.create_chapter(
            chapter_id="ch_2", name="Act Two", started_at_tick=20, theme="war", status="open"
        )

    assert result == "ch_2"
    mock_fn.assert_awaited_once_with(
        session, chapter_id="ch_2", name="Act Two", started_at_tick=20, theme="war", status="open"
    )


@pytest.mark.asyncio
async def test_close_chapter_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jChapterRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.close_chapter", new=AsyncMock()) as mock_fn:
        await repo.close_chapter(chapter_id="ch_1", ended_at_tick=30)

    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session, chapter_id="ch_1", ended_at_tick=30)


@pytest.mark.asyncio
async def test_link_event_to_chapter_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jChapterRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.link_event_to_chapter", new=AsyncMock()) as mock_fn:
        await repo.link_event_to_chapter(event_id="e1", chapter_id="ch_1", tick_id=12)

    mock_fn.assert_awaited_once_with(session, event_id="e1", chapter_id="ch_1", tick_id=12)
