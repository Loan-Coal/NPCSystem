"""Unit tests for Neo4jPledgeRepository (DEC-122 / SEV-24 graph repo seam)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.pledge_repository import Neo4jPledgeRepository

_MOD = "npc_engine.graph.repositories.pledge_repository"


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
async def test_get_expiring_pledges_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jPledgeRepository(db)  # type: ignore[arg-type]
    rows = [{"pledger_id": "a", "pledgee_id": "b", "pledge_type": "fealty"}]

    with patch(f"{_MOD}.get_expiring_pledges_svc", new=AsyncMock(return_value=rows)) as mock_fn:
        result = await repo.get_expiring_pledges(tick_id=9)

    assert result == rows
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session, tick_id=9)


@pytest.mark.asyncio
async def test_break_pledge_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jPledgeRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.break_pledge", new=AsyncMock()) as mock_fn:
        await repo.break_pledge(pledger_id="a", pledgee_id="b", pledge_type="fealty", tick=9)

    mock_fn.assert_awaited_once_with(session, pledger_id="a", pledgee_id="b", pledge_type="fealty", tick=9)


@pytest.mark.asyncio
async def test_check_pledge_violations_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jPledgeRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.check_pledge_violations", new=AsyncMock(return_value=[])) as mock_fn:
        await repo.check_pledge_violations(pledger_id="a", tick=9)

    mock_fn.assert_awaited_once_with(session, pledger_id="a", tick=9)
