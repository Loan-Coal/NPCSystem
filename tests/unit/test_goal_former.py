"""
Unit tests for engines.planning.goal_former.GoalFormer.

Does NOT: connect to Neo4j, call LLMs, or import engine-layer code directly in fixtures.
All graph calls are mocked via unittest.mock.AsyncMock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.planning.goal_former import GoalFormer
from npc_engine.world.time_utils import TimePoint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> MagicMock:
    """Return a MagicMock that behaves like an AsyncSession."""
    return MagicMock()


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


# ---------------------------------------------------------------------------
# Test 1: most-decayed need (lowest level) is selected; urgency = 100 - level
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forms_goal_for_lowest_level_need():
    """GoalFormer picks the need with the lowest level and sets urgency = 100 - level."""
    session = _make_session()
    game_time = _game_time()

    needs = [
        _need("n-low", "hunger", level=20),
        _need("n-high", "social", level=80),
    ]

    with (
        patch(
            "npc_engine.engines.planning.goal_former.get_needs_for_character",
            new=AsyncMock(return_value=needs),
        ),
        patch(
            "npc_engine.engines.planning.goal_former.create_goal",
            new=AsyncMock(return_value="goal-001"),
        ) as mock_create_goal,
        patch(
            "npc_engine.engines.planning.goal_former.get_satisfying_location_for_need",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "npc_engine.engines.planning.goal_former.create_goal_targets_edge",
            new=AsyncMock(),
        ),
    ):
        former = GoalFormer()
        await former.form_goal(session, character_id="char-1", game_time=game_time)

    # urgency = 100 - 20 = 80
    mock_create_goal.assert_awaited_once()
    call_kwargs = mock_create_goal.call_args.kwargs
    assert call_kwargs["urgency"] == 80
    assert call_kwargs["character_id"] == "char-1"


# ---------------------------------------------------------------------------
# Test 2: urgency is clamped to 100 when need.level == 0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_urgency_clamped_when_need_at_zero():
    """Urgency must not exceed 100 even when level is 0 (100 - 0 = 100)."""
    session = _make_session()
    game_time = _game_time()

    needs = [_need("n-zero", "rest", level=0)]

    with (
        patch(
            "npc_engine.engines.planning.goal_former.get_needs_for_character",
            new=AsyncMock(return_value=needs),
        ),
        patch(
            "npc_engine.engines.planning.goal_former.create_goal",
            new=AsyncMock(return_value="goal-002"),
        ) as mock_create_goal,
        patch(
            "npc_engine.engines.planning.goal_former.get_satisfying_location_for_need",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "npc_engine.engines.planning.goal_former.create_goal_targets_edge",
            new=AsyncMock(),
        ),
    ):
        former = GoalFormer()
        await former.form_goal(session, character_id="char-1", game_time=game_time)

    call_kwargs = mock_create_goal.call_args.kwargs
    assert call_kwargs["urgency"] == 100


# ---------------------------------------------------------------------------
# Test 3: GOAL_TARGETS edge written to the satisfying location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_goal_targets_edge_points_to_satisfying_location():
    """When a satisfying location exists, GOAL_TARGETS edge is written with correct target_id."""
    session = _make_session()
    game_time = _game_time()

    needs = [_need("n-social", "social", level=10)]

    with (
        patch(
            "npc_engine.engines.planning.goal_former.get_needs_for_character",
            new=AsyncMock(return_value=needs),
        ),
        patch(
            "npc_engine.engines.planning.goal_former.create_goal",
            new=AsyncMock(return_value="goal-003"),
        ),
        patch(
            "npc_engine.engines.planning.goal_former.get_satisfying_location_for_need",
            new=AsyncMock(return_value="tavern"),
        ),
        patch(
            "npc_engine.engines.planning.goal_former.create_goal_targets_edge",
            new=AsyncMock(),
        ) as mock_edge,
    ):
        former = GoalFormer()
        await former.form_goal(session, character_id="char-1", game_time=game_time)

    mock_edge.assert_awaited_once()
    edge_kwargs = mock_edge.call_args
    # Positional args: session, goal_id, target_id, priority
    assert edge_kwargs.args[2] == "tavern"
