"""Unit tests for Neo4jNeedRepository (DEC-122 / SEV-24 graph repository seam).

Verifies the adapter connects, opens a session per call, and delegates to the
graph query/writer functions — no real Neo4j involved.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.need_repository import Neo4jNeedRepository


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
async def test_get_all_needs_connects_and_delegates():
    """get_all_needs_with_location connects, opens a session, and forwards it."""
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jNeedRepository(db)  # type: ignore[arg-type]
    rows = [{"need_id": "n-1", "level": 50}]

    with patch(
        "npc_engine.graph.repositories.need_repository.get_all_needs_with_location",
        new=AsyncMock(return_value=rows),
    ) as mock_get:
        result = await repo.get_all_needs_with_location()

    assert result == rows
    assert db.connect_calls == 1
    mock_get.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_set_need_level_connects_and_delegates():
    """set_need_level connects, opens a session, and forwards the named args."""
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jNeedRepository(db)  # type: ignore[arg-type]

    with patch(
        "npc_engine.graph.repositories.need_repository.set_need_level",
        new=AsyncMock(),
    ) as mock_set:
        await repo.set_need_level(need_id="n-1", level=42)

    assert db.connect_calls == 1
    mock_set.assert_awaited_once_with(session, need_id="n-1", level=42)
