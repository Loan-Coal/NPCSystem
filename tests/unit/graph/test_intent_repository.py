"""Unit tests for Neo4jIntentRepository (DEC-122 / SEV-24 Wave 3 agenda-others).

Covers the IntentGraphPort adapter against a fake GraphDB (session-per-call seam): each
method opens one session and delegates to the matching intent_queries / intent_queue_writer
function.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.intent_repository import Neo4jIntentRepository

_MOD = "npc_engine.graph.repositories.intent_repository"


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
async def test_get_npc_location_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jIntentRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.get_npc_location", new=AsyncMock(return_value="tavern")) as fn:
        result = await repo.get_npc_location(npc_id="mira")

    assert result == "tavern"
    assert db.connect_calls == 1
    fn.assert_awaited_once_with(db._session, "mira")


@pytest.mark.asyncio
async def test_get_witnessed_events_delegates_since_tick():
    db = _FakeGraphDB(object())
    repo = Neo4jIntentRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.get_witnessed_events", new=AsyncMock(return_value=[{"id": "e1"}])) as fn:
        result = await repo.get_witnessed_events(npc_id="mira", since_tick=5)

    assert result == [{"id": "e1"}]
    fn.assert_awaited_once_with(db._session, "mira", 5)


@pytest.mark.asyncio
async def test_enqueue_intent_delegates_with_settings():
    db = _FakeGraphDB(object())
    repo = Neo4jIntentRepository(db)  # type: ignore[arg-type]
    intent = object()
    settings = object()

    with patch(f"{_MOD}.enqueue_intent", new=AsyncMock()) as fn:
        await repo.enqueue_intent(intent, settings=settings)  # type: ignore[arg-type]

    fn.assert_awaited_once_with(db._session, intent, settings=settings)


@pytest.mark.asyncio
async def test_expire_old_intents_delegates_cutoff():
    db = _FakeGraphDB(object())
    repo = Neo4jIntentRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.expire_old_intents", new=AsyncMock(return_value=3)) as fn:
        result = await repo.expire_old_intents(cutoff_tick=7)

    assert result == 3
    fn.assert_awaited_once_with(db._session, cutoff_tick=7)
