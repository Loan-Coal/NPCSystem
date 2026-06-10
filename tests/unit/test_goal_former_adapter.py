"""
Unit tests for engines.planning.goal_former_adapter.GoalFormerAdapter.

Covers:
- run_tick calls GoalFormer.form_goal for each NPC id returned by get_npc_ids
- run_tick returns a dict with a 'goal_formations' key listing formed goal ids
- run_tick is a no-op when there are no NPCs
- run_tick calls ActionSelector.select_action for each NPC with a formed goal (EXP-51 slice-3)
- run_tick does NOT call ActionSelector for NPCs where form_goal returned None
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


def _world_state_mock() -> MagicMock:
    return MagicMock(year=1, season="spring", day=1, time_of_day="morning")


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
            new=AsyncMock(return_value=_world_state_mock()),
        ),
    ):
        mock_former = MagicMock()
        mock_former.form_goal = AsyncMock(side_effect=[("goal-a", 60, "tavern"), ("goal-b", 70, None)])
        mock_selector = MagicMock()
        mock_selector.select_action = AsyncMock()
        adapter = GoalFormerAdapter(goal_former=mock_former, action_selector=mock_selector)

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
            new=AsyncMock(return_value=_world_state_mock()),
        ),
    ):
        mock_former = MagicMock()
        mock_former.form_goal = AsyncMock(side_effect=[("goal-x", 55, "market_square"), None])
        mock_selector = MagicMock()
        mock_selector.select_action = AsyncMock()
        adapter = GoalFormerAdapter(goal_former=mock_former, action_selector=mock_selector)

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
            new=AsyncMock(return_value=_world_state_mock()),
        ),
    ):
        mock_former = MagicMock()
        mock_former.form_goal = AsyncMock()
        mock_selector = MagicMock()
        mock_selector.select_action = AsyncMock()
        adapter = GoalFormerAdapter(goal_former=mock_former, action_selector=mock_selector)

        result = await adapter.run_tick(session=session, tick_id=3)

    mock_former.form_goal.assert_not_awaited()
    assert result["goal_formations"] == []


@pytest.mark.asyncio
async def test_run_tick_calls_action_selector_for_each_formed_goal() -> None:
    """run_tick must call ActionSelector.select_action once per NPC with a non-None goal."""
    session = _session()

    with (
        patch(
            "npc_engine.engines.planning.goal_former_adapter.get_npc_ids",
            new=AsyncMock(return_value=["npc-1", "npc-2"]),
        ),
        patch(
            "npc_engine.engines.planning.goal_former_adapter.get_world_state",
            new=AsyncMock(return_value=_world_state_mock()),
        ),
    ):
        mock_former = MagicMock()
        mock_former.form_goal = AsyncMock(side_effect=[("goal-a", 80, "tavern"), ("goal-b", 30, None)])
        mock_selector = MagicMock()
        mock_selector.select_action = AsyncMock()
        adapter = GoalFormerAdapter(goal_former=mock_former, action_selector=mock_selector)

        await adapter.run_tick(session=session, tick_id=4)

    assert mock_selector.select_action.await_count == 2
    calls = mock_selector.select_action.call_args_list
    # First call: npc-1 with urgency=80, target_location_id="tavern"
    assert calls[0].kwargs["character_id"] == "npc-1"
    assert calls[0].kwargs["goals"][0]["urgency"] == 80
    assert calls[0].kwargs["goals"][0]["goal_id"] == "goal-a"
    assert calls[0].kwargs["goals"][0]["target_location_id"] == "tavern"
    # Second call: npc-2 with urgency=30, target_location_id=None (no satisfying location)
    assert calls[1].kwargs["character_id"] == "npc-2"
    assert calls[1].kwargs["goals"][0]["urgency"] == 30
    assert calls[1].kwargs["goals"][0]["target_location_id"] is None


@pytest.mark.asyncio
async def test_run_tick_does_not_call_action_selector_when_no_goal() -> None:
    """run_tick must NOT call ActionSelector for NPCs where form_goal returned None."""
    session = _session()

    with (
        patch(
            "npc_engine.engines.planning.goal_former_adapter.get_npc_ids",
            new=AsyncMock(return_value=["npc-1", "npc-2"]),
        ),
        patch(
            "npc_engine.engines.planning.goal_former_adapter.get_world_state",
            new=AsyncMock(return_value=_world_state_mock()),
        ),
    ):
        mock_former = MagicMock()
        mock_former.form_goal = AsyncMock(side_effect=[None, None])
        mock_selector = MagicMock()
        mock_selector.select_action = AsyncMock()
        adapter = GoalFormerAdapter(goal_former=mock_former, action_selector=mock_selector)

        await adapter.run_tick(session=session, tick_id=5)

    mock_selector.select_action.assert_not_awaited()
