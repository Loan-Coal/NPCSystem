"""Unit tests for Neo4jInvestigationRepository (DEC-122 / SEV-24 investigation slice).

Covers the InvestigationGraphPort adapter against a fake GraphDB (session-per-call seam):
each method opens one session and delegates to the matching investigation_queries function.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.investigation_repository import Neo4jInvestigationRepository

_MOD = "npc_engine.graph.repositories.investigation_repository"


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
async def test_get_evidence_for_event_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jInvestigationRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.get_evidence_for_event", new=AsyncMock(return_value=[{"id": "ev"}])) as fn:
        result = await repo.get_evidence_for_event(event_id="e1")

    assert result == [{"id": "ev"}]
    assert db.connect_calls == 1
    fn.assert_awaited_once_with(db._session, "e1")


@pytest.mark.asyncio
async def test_get_deductions_for_character_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jInvestigationRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.get_deductions_for_character", new=AsyncMock(return_value=[])) as fn:
        result = await repo.get_deductions_for_character(character_id="c1")

    assert result == []
    fn.assert_awaited_once_with(db._session, "c1")


@pytest.mark.asyncio
async def test_get_alibi_window_delegates_window_bounds():
    db = _FakeGraphDB(object())
    repo = Neo4jInvestigationRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.get_alibi_window", new=AsyncMock(return_value=[{"location": {}}])) as fn:
        result = await repo.get_alibi_window(character_id="c1", from_tick=3, to_tick=9)

    assert result == [{"location": {}}]
    fn.assert_awaited_once_with(db._session, character_id="c1", from_tick=3, to_tick=9)


@pytest.mark.asyncio
async def test_get_contradicting_rumors_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jInvestigationRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.get_contradicting_rumors", new=AsyncMock(return_value=[])) as fn:
        result = await repo.get_contradicting_rumors(event_id="e1")

    assert result == []
    fn.assert_awaited_once_with(db._session, "e1")
