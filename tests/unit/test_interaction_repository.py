"""Unit tests for Neo4jInteractionRepository (DEC-122 / SEV-24 interaction slice).

Covers the InteractionGraphPort adapter against a fake GraphDB (session-per-call seam):
each method opens one session and delegates to the matching graph query/writer function.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.interaction_repository import Neo4jInteractionRepository

_MOD = "npc_engine.graph.repositories.interaction_repository"


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
async def test_get_quest_state_delegates_keyword_args():
    db = _FakeGraphDB(object())
    repo = Neo4jInteractionRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.get_quest_state", new=AsyncMock(return_value={"quest_id": "q1"})) as fn:
        result = await repo.get_quest_state(quest_id="q1", player_id="p1")

    assert result == {"quest_id": "q1"}
    assert db.connect_calls == 1
    fn.assert_awaited_once_with(session=db._session, quest_id="q1", player_id="p1")


@pytest.mark.asyncio
async def test_get_active_quest_for_player_delegates_positional():
    db = _FakeGraphDB(object())
    repo = Neo4jInteractionRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.get_active_quest_for_player", new=AsyncMock(return_value=None)) as fn:
        result = await repo.get_active_quest_for_player(player_id="p1")

    assert result is None
    fn.assert_awaited_once_with(db._session, "p1")


@pytest.mark.asyncio
async def test_count_player_has_item_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jInteractionRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.count_player_has_item", new=AsyncMock(return_value=3)) as fn:
        result = await repo.count_player_has_item(player_id="p1", item_id="amulet")

    assert result == 3
    fn.assert_awaited_once_with(db._session, player_id="p1", item_id="amulet")


@pytest.mark.asyncio
async def test_count_player_located_at_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jInteractionRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.count_player_located_at", new=AsyncMock(return_value=1)) as fn:
        result = await repo.count_player_located_at(player_id="p1", location_id="loc")

    assert result == 1
    fn.assert_awaited_once_with(db._session, player_id="p1", location_id="loc")


@pytest.mark.asyncio
async def test_count_target_inactive_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jInteractionRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.count_target_inactive", new=AsyncMock(return_value=0)) as fn:
        result = await repo.count_target_inactive(target_id="npc_x")

    assert result == 0
    fn.assert_awaited_once_with(db._session, target_id="npc_x")


@pytest.mark.asyncio
async def test_count_player_co_located_with_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jInteractionRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.count_player_co_located_with", new=AsyncMock(return_value=1)) as fn:
        result = await repo.count_player_co_located_with(player_id="p1", target_id="npc_y")

    assert result == 1
    fn.assert_awaited_once_with(db._session, player_id="p1", target_id="npc_y")
