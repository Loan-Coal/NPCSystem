"""Unit tests for intent_queue_reader (Phase 14 S14.2)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.graph.intent.intent_queue_reader import get_pending_intents

_READER_MOD = "npc_engine.graph.intent.intent_queue_reader"

_ROW_A = {
    "id": "npc1:player1:5:need",
    "npc_id": "npc1",
    "player_id": "player1",
    "tick": 5,
    "score": 0.9,
    "reason": "I need help with hunger",
    "trigger_type": "need",
    "trigger_ref": "need-food",
    "created_tick": 5,
}
_ROW_B = {
    "id": "npc2:player1:5:goal",
    "npc_id": "npc2",
    "player_id": "player1",
    "tick": 5,
    "score": 0.6,
    "reason": "There's something I need to discuss: Find the heir",
    "trigger_type": "goal",
    "trigger_ref": "goal-heir",
    "created_tick": 5,
}


def _fake_settings(max_per_player: int = 10) -> MagicMock:
    s = MagicMock()
    s.MAX_PENDING_INTENTS_PER_PLAYER = max_per_player
    return s


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_get_pending_returns_intents_as_models(session):
    """Returns a list of ConversationIntent models, not raw dicts."""
    with patch(f"{_READER_MOD}.get_pending_for_player", new=AsyncMock(return_value=[_ROW_A])):
        intents = await get_pending_intents(session, "player1", settings=_fake_settings())

    assert len(intents) == 1
    assert intents[0].npc_id == "npc1"
    assert intents[0].trigger_type == "need"
    assert intents[0].score == 0.9


@pytest.mark.asyncio
async def test_get_pending_returns_ordered_by_score_desc(session):
    """Results preserve the score DESC order returned by the graph layer."""
    with patch(
        f"{_READER_MOD}.get_pending_for_player",
        new=AsyncMock(return_value=[_ROW_A, _ROW_B]),
    ):
        intents = await get_pending_intents(session, "player1", settings=_fake_settings())

    assert intents[0].score > intents[1].score


@pytest.mark.asyncio
async def test_get_pending_respects_player_limit(session):
    """Passes MAX_PENDING_INTENTS_PER_PLAYER as the limit to the query function."""
    with patch(
        f"{_READER_MOD}.get_pending_for_player",
        new=AsyncMock(return_value=[]),
    ) as mock_get:
        await get_pending_intents(session, "player1", settings=_fake_settings(max_per_player=3))

    call_kwargs = mock_get.call_args
    assert call_kwargs.kwargs.get("limit") == 3 or call_kwargs.args[-1] == 3


@pytest.mark.asyncio
async def test_get_pending_returns_empty_list_when_none(session):
    """Returns [] when no pending intents exist for the player."""
    with patch(f"{_READER_MOD}.get_pending_for_player", new=AsyncMock(return_value=[])):
        intents = await get_pending_intents(session, "player1", settings=_fake_settings())

    assert intents == []
