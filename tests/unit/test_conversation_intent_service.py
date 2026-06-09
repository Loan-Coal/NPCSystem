"""Unit tests for conversation_intent_service (Phase 14 S14.1)."""
from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.engines.agenda.conversation_intent_service import score_intents

_NPC_ID = "captain_sorn"
_PLAYER_ID = "player1"
_TICK = 10
_LOCATION = "guard_barracks"

_MODULE = "npc_engine.engines.agenda.conversation_intent_service"


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


def _patches(
    npc_loc: str | None = _LOCATION,
    player_loc: str | None = _LOCATION,
    needs: list | None = None,
    events: list | None = None,
    goals: list | None = None,
) -> ExitStack:
    """Return an ExitStack with all graph query imports patched."""
    stack = ExitStack()
    stack.enter_context(patch(f"{_MODULE}.get_npc_location", new=AsyncMock(return_value=npc_loc)))
    stack.enter_context(patch(f"{_MODULE}.get_player_location", new=AsyncMock(return_value=player_loc)))
    stack.enter_context(patch(f"{_MODULE}.get_unmet_needs", new=AsyncMock(return_value=needs or [])))
    stack.enter_context(patch(f"{_MODULE}.get_witnessed_events", new=AsyncMock(return_value=events or [])))
    stack.enter_context(patch(f"{_MODULE}.get_unresolved_goals", new=AsyncMock(return_value=goals or [])))
    return stack


# ---------------------------------------------------------------------------
# Happy path — one trigger type fires per test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_need_trigger_emits_intent(session):
    """A low-level need (level=20) yields a need intent with score 0.8."""
    need = {"id": "need-food", "kind": "hunger", "level": 20, "decay_rate": 5, "character_id": _NPC_ID}
    with _patches(needs=[need]):
        intents = await score_intents(session, _NPC_ID, _PLAYER_ID, _TICK)

    assert len(intents) == 1
    assert intents[0].trigger_type == "need"
    assert intents[0].trigger_ref == "need-food"
    assert abs(intents[0].score - 0.8) < 0.01


@pytest.mark.asyncio
async def test_event_trigger_emits_intent(session):
    """A recent event (2 ticks ago) yields an event intent above threshold."""
    event = {"id": "evt-war", "summary": "Northern war begins", "learned_at_tick": _TICK - 2}
    with _patches(events=[event]):
        intents = await score_intents(session, _NPC_ID, _PLAYER_ID, _TICK)

    assert len(intents) == 1
    assert intents[0].trigger_type == "event"
    assert intents[0].trigger_ref == "evt-war"
    assert intents[0].score > 0.3


@pytest.mark.asyncio
async def test_goal_trigger_emits_intent(session):
    """An urgent goal (urgency=80) yields a goal intent with score 0.8."""
    goal = {"id": "goal-find-heir", "description": "Find the lost heir", "urgency": 80, "status": "active"}
    with _patches(goals=[goal]):
        intents = await score_intents(session, _NPC_ID, _PLAYER_ID, _TICK)

    assert len(intents) == 1
    assert intents[0].trigger_type == "goal"
    assert intents[0].trigger_ref == "goal-find-heir"
    assert abs(intents[0].score - 0.8) < 0.01


# ---------------------------------------------------------------------------
# Threshold and co-location guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_below_threshold_emits_nothing(session):
    """Items scoring below MIN_INTENT_SCORE (0.3) produce no intents.

    need.level=75 → 0.25; event learned_at_tick=0 at tick=25 with default
    INTENT_EXPIRY_TICKS=20 → score≤0; goal.urgency=10 → 0.1.
    """
    need = {"id": "n1", "kind": "rest", "level": 75, "decay_rate": 1, "character_id": _NPC_ID}
    event = {"id": "e1", "summary": "Old news", "learned_at_tick": 0}
    goal = {"id": "g1", "description": "Low priority task", "urgency": 10, "status": "active"}
    with _patches(needs=[need], events=[event], goals=[goal]):
        intents = await score_intents(session, _NPC_ID, _PLAYER_ID, 25)

    assert intents == []


@pytest.mark.asyncio
async def test_different_location_emits_nothing(session):
    """NPC and player at different locations yield an empty list immediately."""
    need = {"id": "n1", "kind": "hunger", "level": 5, "decay_rate": 5, "character_id": _NPC_ID}
    with _patches(npc_loc="barracks", player_loc="market", needs=[need]):
        intents = await score_intents(session, _NPC_ID, _PLAYER_ID, _TICK)

    assert intents == []
