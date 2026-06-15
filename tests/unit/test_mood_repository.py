"""Unit tests for Neo4jMoodRepository (DEC-122 / SEV-24 graph repository seam).

Verifies the adapter connects, opens a session per call, and delegates to the
mood graph queries — no real Neo4j involved.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.mood_repository import Neo4jMoodRepository


class _FakeGraphDB:
    """Minimal GraphDB stand-in recording connect() and yielding a fixed session."""

    def __init__(self, session: Any) -> None:
        self._session = session
        self.connect_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[Any]:
        yield self._session


@pytest.mark.asyncio
async def test_get_pairs_connects_and_delegates():
    """get_co_located_affectionate_pairs connects, opens a session, forwards threshold."""
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMoodRepository(db)  # type: ignore[arg-type]
    pairs = [("a", "b")]

    with patch(
        "npc_engine.graph.repositories.mood_repository.get_co_located_affectionate_pairs",
        new=AsyncMock(return_value=pairs),
    ) as mock_pairs:
        result = await repo.get_co_located_affectionate_pairs(affection_threshold=50)

    assert result == pairs
    assert db.connect_calls == 1
    mock_pairs.assert_awaited_once_with(session, affection_threshold=50)


@pytest.mark.asyncio
async def test_set_mood_connects_and_delegates():
    """set_character_mood connects, opens a session, and forwards the named args."""
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMoodRepository(db)  # type: ignore[arg-type]

    with patch(
        "npc_engine.graph.repositories.mood_repository.set_character_mood",
        new=AsyncMock(),
    ) as mock_set:
        await repo.set_character_mood(character_id="npc_a", mood="warm", intensity=0.4)

    assert db.connect_calls == 1
    mock_set.assert_awaited_once_with(session, character_id="npc_a", mood="warm", intensity=0.4)


@pytest.mark.asyncio
async def test_get_all_moods_connects_and_delegates():
    """get_all_character_moods connects, opens a session, and returns the rows."""
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMoodRepository(db)  # type: ignore[arg-type]
    moods = [{"character_id": "npc_a", "mood": "warm", "intensity": 0.4}]

    with patch(
        "npc_engine.graph.repositories.mood_repository.get_all_character_moods",
        new=AsyncMock(return_value=moods),
    ) as mock_get:
        result = await repo.get_all_character_moods()

    assert result == moods
    assert db.connect_calls == 1
    mock_get.assert_awaited_once_with(session)
