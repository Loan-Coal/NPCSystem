"""Unit tests for IntentFormationEngine (SEV-24 Wave 3 agenda-others).

The engine mocks the PlayerLocationReadPort + IntentGraphPort (no Neo4j session); covers
the happy path (score → enqueue → expire) and the ignored scheduler ``session=`` kwarg.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from npc_engine.common.intent_models import ConversationIntent
from npc_engine.engines.agenda.intent_formation_engine import IntentFormationEngine

_NPC_ID = "captain_sorn"
_PLAYER_ID = "player1"
_TICK = 10


def _intent(score: float = 0.8) -> ConversationIntent:
    return ConversationIntent(
        npc_id=_NPC_ID,
        player_id=_PLAYER_ID,
        tick=_TICK,
        score=score,
        reason="I need help with hunger",
        trigger_type="need",
        trigger_ref="need-food",
    )


@pytest.mark.asyncio
async def test_run_tick_scores_enqueues_and_expires():
    """One co-located pair with one unmet need enqueues one intent and reports expiry."""
    location_reader = AsyncMock()
    location_reader.get_collocated_pairs = AsyncMock(return_value=[(_NPC_ID, _PLAYER_ID)])

    repo = AsyncMock()
    repo.get_npc_location = AsyncMock(return_value="guard_barracks")
    repo.get_player_location = AsyncMock(return_value="guard_barracks")
    repo.get_unmet_needs = AsyncMock(
        return_value=[{"id": "need-food", "kind": "hunger", "level": 20}]
    )
    repo.get_witnessed_events = AsyncMock(return_value=[])
    repo.get_unresolved_goals = AsyncMock(return_value=[])
    repo.enqueue_intent = AsyncMock()
    repo.expire_old_intents = AsyncMock(return_value=2)

    engine = IntentFormationEngine(location_reader=location_reader, intent_repo=repo)
    result = await engine.run_tick(tick_id=_TICK)

    assert result == {"intents_formed": 1, "expired": 2}
    repo.enqueue_intent.assert_awaited_once()
    repo.expire_old_intents.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_tick_ignores_scheduler_session_kwarg():
    """The scheduler passes ``session=``; run_tick must accept and ignore it."""
    location_reader = AsyncMock()
    location_reader.get_collocated_pairs = AsyncMock(return_value=[])
    repo = AsyncMock()
    repo.expire_old_intents = AsyncMock(return_value=0)

    engine = IntentFormationEngine(location_reader=location_reader, intent_repo=repo)
    result = await engine.run_tick(session=object(), tick_id=_TICK)

    assert result == {"intents_formed": 0, "expired": 0}
    location_reader.get_collocated_pairs.assert_awaited_once_with()
