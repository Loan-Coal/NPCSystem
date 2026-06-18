"""Unit tests for Neo4jPlanningRepository (DEC-122 / SEV-24 Wave 3).

Covers the PlanningGraphPort adapter against a fake GraphDB (session-per-call seam): each
method opens one session and delegates to the matching graph query/writer function.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.planning_repository import Neo4jPlanningRepository
from npc_engine.world.time_utils import TimePoint

_MOD = "npc_engine.graph.repositories.planning_repository"


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
async def test_get_needs_for_character_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jPlanningRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.get_needs_for_character", new=AsyncMock(return_value=[{"x": 1}])) as fn:
        result = await repo.get_needs_for_character(character_id="c1")

    assert result == [{"x": 1}]
    assert db.connect_calls == 1
    fn.assert_awaited_once_with(session, "c1")


@pytest.mark.asyncio
async def test_get_satisfying_location_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jPlanningRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.get_satisfying_location_for_need", new=AsyncMock(return_value="tavern")) as fn:
        result = await repo.get_satisfying_location_for_need(need_kind="social")

    assert result == "tavern"
    fn.assert_awaited_once_with(db._session, "social")


@pytest.mark.asyncio
async def test_create_goal_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jPlanningRepository(db)  # type: ignore[arg-type]
    gt = TimePoint(year=1, season="spring", day=1, time_of_day="morning")

    with patch(f"{_MOD}.create_goal", new=AsyncMock(return_value="goal-1")) as fn:
        result = await repo.create_goal(
            character_id="c1", description="satisfy hunger need", urgency=80, game_time=gt
        )

    assert result == "goal-1"
    fn.assert_awaited_once_with(
        db._session, character_id="c1", description="satisfy hunger need", urgency=80, game_time=gt
    )


@pytest.mark.asyncio
async def test_create_goal_targets_edge_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jPlanningRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.create_goal_targets_edge", new=AsyncMock()) as fn:
        await repo.create_goal_targets_edge(goal_id="goal-1", target_id="tavern", priority=80)

    fn.assert_awaited_once_with(db._session, "goal-1", "tavern", 80)


@pytest.mark.asyncio
async def test_move_character_delegates():
    db = _FakeGraphDB(object())
    repo = Neo4jPlanningRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.update_character_location", new=AsyncMock()) as fn:
        await repo.move_character(character_id="c1", location_id="tavern")

    fn.assert_awaited_once_with(db._session, character_id="c1", location_id="tavern")
