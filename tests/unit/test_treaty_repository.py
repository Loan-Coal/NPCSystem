"""Unit tests for Neo4jTreatyRepository (DEC-122 / SEV-24 graph repo seam)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.treaty_repository import Neo4jTreatyRepository

_MOD = "npc_engine.graph.repositories.treaty_repository"


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
async def test_get_expiring_treaties_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jTreatyRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.get_expiring_treaties_svc", new=AsyncMock(return_value=["t1"])) as mock_fn:
        result = await repo.get_expiring_treaties(tick_id=9)

    assert result == ["t1"]
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session, tick_id=9)


@pytest.mark.asyncio
async def test_expire_treaty_delegates_positional():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jTreatyRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.expire_treaty", new=AsyncMock()) as mock_fn:
        await repo.expire_treaty(treaty_id="t1", tick_id=9)

    mock_fn.assert_awaited_once_with(session, "t1", 9)


@pytest.mark.asyncio
async def test_check_conditions_delegates_positional():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jTreatyRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.check_treaty_conditions_mechanical", new=AsyncMock(return_value=[])) as mock_fn:
        await repo.check_treaty_conditions_mechanical(treaty_id="t1", tick_id=9)

    mock_fn.assert_awaited_once_with(session, "t1", 9)
