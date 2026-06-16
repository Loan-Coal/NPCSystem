"""
Unit tests for engines.planning.action_selector.ActionSelector.

ActionSelector depends on an injected PlanningGraphPort (DEC-122 / SEV-24) and holds no
session. The move write is mocked via an AsyncMock port double.

Does NOT: connect to Neo4j, call LLMs, or open sessions.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.planning.action_selector import ActionSelector


def _goal(goal_id: str, urgency: int, target_location_id: str | None = "tavern") -> dict:
    return {
        "goal_id": goal_id,
        "urgency": urgency,
        "status": "active",
        "target_location_id": target_location_id,
    }


@pytest.mark.asyncio
async def test_high_urgency_goal_overrides_routine():
    """When goal urgency > ROUTINE_PRIORITY the selector calls move_character."""
    port = AsyncMock()
    goals = [_goal("g-high", urgency=90, target_location_id="tavern")]

    await ActionSelector(planning_repo=port).select_action(character_id="char-1", goals=goals)

    port.move_character.assert_awaited_once_with(character_id="char-1", location_id="tavern")


@pytest.mark.asyncio
async def test_low_urgency_goal_defers_to_routine():
    """When goal urgency <= ROUTINE_PRIORITY the selector is a no-op (routine keeps control)."""
    port = AsyncMock()
    goals = [_goal("g-low", urgency=30, target_location_id="market")]

    await ActionSelector(planning_repo=port).select_action(character_id="char-1", goals=goals)

    port.move_character.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_target_location_skips_move():
    """A high-urgency goal with no target location dispatches no move."""
    port = AsyncMock()
    goals = [_goal("g-high", urgency=90, target_location_id=None)]

    await ActionSelector(planning_repo=port).select_action(character_id="char-1", goals=goals)

    port.move_character.assert_not_awaited()
