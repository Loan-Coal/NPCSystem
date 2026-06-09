"""Unit tests for intent_queue_writer (Phase 14 S14.2)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.common.intent_models import ConversationIntent
from npc_engine.graph.intent_queue_writer import enqueue_intent, expire_old_intents, mark_delivered

_WRITER_MOD = "npc_engine.graph.intent_queue_writer"

_INTENT = ConversationIntent(
    npc_id="captain_sorn",
    player_id="player1",
    tick=5,
    score=0.8,
    reason="I need help with hunger",
    trigger_type="need",
    trigger_ref="need-food",
)


def _fake_settings(max_per_npc: int = 5) -> MagicMock:
    s = MagicMock()
    s.MAX_PENDING_INTENTS_PER_NPC = max_per_npc
    return s


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


# ---------------------------------------------------------------------------
# enqueue_intent — normal path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_calls_merge_when_under_cap(session):
    """When NPC is under cap, merge_pending_intent is called with correct params."""
    with (
        patch(f"{_WRITER_MOD}.count_npc_pending_intents", new=AsyncMock(return_value=0)),
        patch(f"{_WRITER_MOD}.merge_pending_intent", new=AsyncMock()) as mock_merge,
        patch(f"{_WRITER_MOD}.get_lowest_score_pending", new=AsyncMock(return_value=None)),
        patch(f"{_WRITER_MOD}.delete_intent_by_id", new=AsyncMock()),
    ):
        await enqueue_intent(session, _INTENT, settings=_fake_settings())

    mock_merge.assert_called_once()
    call_kwargs = mock_merge.call_args.kwargs
    assert call_kwargs["npc_id"] == "captain_sorn"
    assert call_kwargs["player_id"] == "player1"
    assert call_kwargs["trigger_type"] == "need"
    assert call_kwargs["score"] == 0.8


@pytest.mark.asyncio
async def test_enqueue_id_format(session):
    """Merged intent id encodes npc_id:player_id:tick:trigger_type."""
    with (
        patch(f"{_WRITER_MOD}.count_npc_pending_intents", new=AsyncMock(return_value=0)),
        patch(f"{_WRITER_MOD}.merge_pending_intent", new=AsyncMock()) as mock_merge,
        patch(f"{_WRITER_MOD}.get_lowest_score_pending", new=AsyncMock(return_value=None)),
        patch(f"{_WRITER_MOD}.delete_intent_by_id", new=AsyncMock()),
    ):
        await enqueue_intent(session, _INTENT, settings=_fake_settings())

    call_kwargs = mock_merge.call_args.kwargs
    assert call_kwargs["id"] == "captain_sorn:player1:5:need"


# ---------------------------------------------------------------------------
# enqueue_intent — cap enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_evicts_lowest_when_at_cap_and_new_score_higher(session):
    """At cap, the lowest-score intent is deleted when new score is higher."""
    lowest = {"id": "old-id", "score": 0.4}
    with (
        patch(f"{_WRITER_MOD}.count_npc_pending_intents", new=AsyncMock(return_value=5)),
        patch(f"{_WRITER_MOD}.get_lowest_score_pending", new=AsyncMock(return_value=lowest)),
        patch(f"{_WRITER_MOD}.delete_intent_by_id", new=AsyncMock()) as mock_delete,
        patch(f"{_WRITER_MOD}.merge_pending_intent", new=AsyncMock()),
    ):
        await enqueue_intent(session, _INTENT, settings=_fake_settings(max_per_npc=5))

    mock_delete.assert_called_once_with(session, "old-id")


@pytest.mark.asyncio
async def test_enqueue_drops_new_when_at_cap_and_new_score_lower(session):
    """At cap, the new intent is dropped (not merged) when its score is lower than lowest."""
    lower_intent = ConversationIntent(
        npc_id="captain_sorn",
        player_id="player1",
        tick=5,
        score=0.2,
        reason="Low priority",
        trigger_type="goal",
        trigger_ref="goal-1",
    )
    lowest = {"id": "existing-id", "score": 0.5}
    with (
        patch(f"{_WRITER_MOD}.count_npc_pending_intents", new=AsyncMock(return_value=5)),
        patch(f"{_WRITER_MOD}.get_lowest_score_pending", new=AsyncMock(return_value=lowest)),
        patch(f"{_WRITER_MOD}.delete_intent_by_id", new=AsyncMock()) as mock_delete,
        patch(f"{_WRITER_MOD}.merge_pending_intent", new=AsyncMock()) as mock_merge,
    ):
        await enqueue_intent(session, lower_intent, settings=_fake_settings(max_per_npc=5))

    mock_delete.assert_not_called()
    mock_merge.assert_not_called()


# ---------------------------------------------------------------------------
# expire_old_intents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expire_returns_count(session):
    """expire_old_intents returns the count of expired intents from the graph layer."""
    with patch(f"{_WRITER_MOD}.expire_stale_intents", new=AsyncMock(return_value=3)) as mock_expire:
        result = await expire_old_intents(session, cutoff_tick=10)

    assert result == 3
    mock_expire.assert_called_once_with(session, cutoff_tick=10)


# ---------------------------------------------------------------------------
# mark_delivered
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_delivered_delegates_to_query(session):
    """mark_delivered calls mark_intent_delivered with the given intent_id."""
    with patch(f"{_WRITER_MOD}.mark_intent_delivered", new=AsyncMock()) as mock_mark:
        await mark_delivered(session, "captain_sorn:player1:5:need")

    mock_mark.assert_called_once_with(session, "captain_sorn:player1:5:need")
