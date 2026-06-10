"""
Unit tests for engines.planning.goal_former_adapter.GoalFormerAdapter.

Covers:
- run_tick calls GoalFormer.form_goal for each NPC id returned by get_npc_ids
- run_tick returns a dict with a 'goal_formations' key listing formed goal ids
- run_tick is a no-op when there are no NPCs
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.planning.goal_former_adapter import GoalFormerAdapter
from npc_engine.world.time_utils import TimePoint


def _session() -> MagicMock:
    return MagicMock()


def _game_time() -> TimePoint:
    return TimePoint(year=1, season="spring", day=1, time_of_day="morning")


@pytest.mark.asyncio
async def test_run_tick_calls_form_goal_for_each_npc() -> None:
    """run_tick must call GoalFormer.form_goal once per NPC returned by get_npc_ids."""
    session = _session()

    with (
        patch(
            "npc_engine.engines.planning.goal_former_adapter.get_npc_ids",
            new=AsyncMock(return_value=["npc-1", "npc-2"]),
        ),
        patch(
            "npc_engine.engines.planning.goal_former_adapter.get_world_state",
            new=AsyncMock(return_value=MagicMock(
                year=1, season="spring", day=1, time_of_day="morning"
            )),
        ),
    ):
        mock_former = MagicMock()
        mock_former.form_goal = AsyncMock(side_effect=["goal-a", "goal-b"])
        adapter = GoalFormerAdapter(goal_former=mock_former)

        result = await adapter.run_tick(session=session, tick_id=1)

    assert mock_former.form_goal.await_count == 2
    assert result["goal_formations"] == ["goal-a", "goal-b"]


@pytest.mark.asyncio
async def test_run_tick_skips_none_goal_ids() -> None:
    """run_tick must omit None results from form_goal (NPC had no needs)."""
    session = _session()

    with (
        patch(
            "npc_engine.engines.planning.goal_former_adapter.get_npc_ids",
            new=AsyncMock(return_value=["npc-1", "npc-2"]),
        ),
        patch(
            "npc_engine.engines.planning.goal_former_adapter.get_world_state",
            new=AsyncMock(return_value=MagicMock(
                year=1, season="spring", day=1, time_of_day="morning"
            )),
        ),
    ):
        mock_former = MagicMock()
        mock_former.form_goal = AsyncMock(side_effect=["goal-x", None])
        adapter = GoalFormerAdapter(goal_former=mock_former)

        result = await adapter.run_tick(session=session, tick_id=2)

    assert result["goal_formations"] == ["goal-x"]


@pytest.mark.asyncio
async def test_run_tick_returns_empty_when_no_npcs() -> None:
    """run_tick must return empty goal_formations when there are no active NPCs."""
    session = _session()

    with (
        patch(
            "npc_engine.engines.planning.goal_former_adapter.get_npc_ids",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.planning.goal_former_adapter.get_world_state",
            new=AsyncMock(return_value=MagicMock(
                year=1, season="spring", day=1, time_of_day="morning"
            )),
        ),
    ):
        mock_former = MagicMock()
        mock_former.form_goal = AsyncMock()
        adapter = GoalFormerAdapter(goal_former=mock_former)

        result = await adapter.run_tick(session=session, tick_id=3)

    mock_former.form_goal.assert_not_awaited()
    assert result["goal_formations"] == []
