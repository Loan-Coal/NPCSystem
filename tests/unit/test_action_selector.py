"""
Unit tests for engines.planning.action_selector.ActionSelector.

Does NOT: connect to Neo4j, call LLMs, or open sessions.
All graph calls are mocked via unittest.mock.AsyncMock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.planning.action_selector import ActionSelector
from npc_engine.engines.planning.action_priority import ROUTINE_PRIORITY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> MagicMock:
    """Return a MagicMock that behaves like an AsyncSession."""
    return MagicMock()


def _goal(goal_id: str, urgency: int, target_location_id: str | None = "tavern") -> dict:
    return {
        "goal_id": goal_id,
        "urgency": urgency,
        "status": "active",
        "target_location_id": target_location_id,
    }


# ---------------------------------------------------------------------------
# Test 4: high-urgency goal (> ROUTINE_PRIORITY) triggers move
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_high_urgency_goal_overrides_routine():
    """When goal urgency > ROUTINE_PRIORITY the selector calls update_character_location."""
    session = _make_session()
    goals = [_goal("g-high", urgency=90, target_location_id="tavern")]

    with (
        patch(
            "npc_engine.engines.planning.action_selector.update_character_location",
            new=AsyncMock(),
        ) as mock_move,
    ):
        selector = ActionSelector()
        await selector.select_action(session, character_id="char-1", goals=goals)

    mock_move.assert_awaited_once()
    call_kwargs = mock_move.call_args
    assert call_kwargs.kwargs.get("character_id") == "char-1" or call_kwargs.args[1] == "char-1"


# ---------------------------------------------------------------------------
# Test 5: low-urgency goal (<= ROUTINE_PRIORITY) does NOT trigger move
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_low_urgency_goal_defers_to_routine():
    """When goal urgency <= ROUTINE_PRIORITY the selector is a no-op (routine keeps control)."""
    session = _make_session()
    goals = [_goal("g-low", urgency=30, target_location_id="market")]

    with (
        patch(
            "npc_engine.engines.planning.action_selector.update_character_location",
            new=AsyncMock(),
        ) as mock_move,
    ):
        selector = ActionSelector()
        await selector.select_action(session, character_id="char-1", goals=goals)

    mock_move.assert_not_awaited()
