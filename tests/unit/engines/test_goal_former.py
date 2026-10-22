"""
Unit tests for engines.planning.goal_former.GoalFormer.

GoalFormer depends on an injected PlanningGraphPort (DEC-122 / SEV-24) and holds no
session. All graph access is mocked via an AsyncMock port double.

Does NOT: connect to Neo4j, call LLMs, or open sessions.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.planning.goal_former import GoalFormer
from npc_engine.world.time_utils import TimePoint


def _game_time() -> TimePoint:
    return TimePoint(year=1, season="spring", day=1, time_of_day="morning")


def _need(need_id: str, kind: str, level: int, character_id: str = "char-1") -> dict:
    return {
        "need_id": need_id,
        "kind": kind,
        "level": level,
        "decay_rate": 5,
        "character_id": character_id,
    }


def _port(needs: list[dict], goal_id: str = "goal-001", location: str | None = None) -> AsyncMock:
    port = AsyncMock()
    port.get_needs_for_character.return_value = needs
    port.create_goal.return_value = goal_id
    port.get_satisfying_location_for_need.return_value = location
    return port


@pytest.mark.asyncio
async def test_forms_goal_for_lowest_level_need():
    """GoalFormer picks the need with the lowest level and sets urgency = 100 - level."""
    needs = [_need("n-low", "hunger", level=20), _need("n-high", "social", level=80)]
    port = _port(needs)

    await GoalFormer(planning_repo=port).form_goal(character_id="char-1", game_time=_game_time())

    # urgency = 100 - 20 = 80
    port.create_goal.assert_awaited_once()
    call_kwargs = port.create_goal.call_args.kwargs
    assert call_kwargs["urgency"] == 80
    assert call_kwargs["character_id"] == "char-1"


@pytest.mark.asyncio
async def test_urgency_clamped_when_need_at_zero():
    """Urgency must not exceed 100 even when level is 0 (100 - 0 = 100)."""
    port = _port([_need("n-zero", "rest", level=0)], goal_id="goal-002")

    await GoalFormer(planning_repo=port).form_goal(character_id="char-1", game_time=_game_time())

    assert port.create_goal.call_args.kwargs["urgency"] == 100


@pytest.mark.asyncio
async def test_goal_targets_edge_points_to_satisfying_location():
    """When a satisfying location exists, GOAL_TARGETS edge is written with correct target_id."""
    port = _port([_need("n-social", "social", level=10)], goal_id="goal-003", location="tavern")

    await GoalFormer(planning_repo=port).form_goal(character_id="char-1", game_time=_game_time())

    port.create_goal_targets_edge.assert_awaited_once()
    assert port.create_goal_targets_edge.call_args.kwargs["target_id"] == "tavern"


@pytest.mark.asyncio
async def test_no_needs_returns_none_and_writes_nothing():
    """A character with no needs forms no goal."""
    port = _port([])

    result = await GoalFormer(planning_repo=port).form_goal(
        character_id="char-1", game_time=_game_time()
    )

    assert result is None
    port.create_goal.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_satisfying_location_called_with_character_id():
    """GoalFormer must pass character_id to get_satisfying_location_for_need."""
    port = _port([_need("n-hunger", "hunger", level=30)], goal_id="goal-001", location="market")

    await GoalFormer(planning_repo=port).form_goal(character_id="char-1", game_time=_game_time())

    port.get_satisfying_location_for_need.assert_awaited_once_with(
        character_id="char-1", need_kind="hunger"
    )


@pytest.mark.asyncio
async def test_two_npcs_get_different_satisfier_locations():
    """Two NPCs with different needs must each pass their own character_id to the satisfier query."""
    port_a = _port([_need("n-social", "social", level=10)], goal_id="goal-a", location="loc_tavern")
    port_b = _port([_need("n-hunger", "hunger", level=20)], goal_id="goal-b", location="loc_market")

    _, _, loc_a = await GoalFormer(planning_repo=port_a).form_goal(
        character_id="char-a", game_time=_game_time()
    )
    _, _, loc_b = await GoalFormer(planning_repo=port_b).form_goal(
        character_id="char-b", game_time=_game_time()
    )

    port_a.get_satisfying_location_for_need.assert_awaited_once_with(
        character_id="char-a", need_kind="social"
    )
    port_b.get_satisfying_location_for_need.assert_awaited_once_with(
        character_id="char-b", need_kind="hunger"
    )
    assert loc_a != loc_b
