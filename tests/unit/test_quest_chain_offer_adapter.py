"""
Unit tests for engines.quest.quest_chain_offer_adapter.QuestChainOfferAdapter.

Covers:
- offer_quest fetches the quest node description and calls QuestOfferService
- offer_quest uses a deterministic idempotency_key derived from quest_id + player_id
- offer_quest raises QuestTransitionError when quest node not found
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.quest.quest_chain_offer_adapter import QuestChainOfferAdapter


def _make_chain_repo(quest_node: dict | None) -> MagicMock:
    """Return a mock QuestChainGraphPort whose get_quest returns quest_node."""
    repo = MagicMock()
    repo.get_quest = AsyncMock(return_value=quest_node)
    return repo


@pytest.mark.asyncio
async def test_offer_quest_calls_offer_service_with_description_as_title() -> None:
    """Adapter must call offer_service.offer_quest with quest description as title."""
    mock_offer_service = MagicMock()
    mock_offer_service.offer_quest = AsyncMock(return_value={"status": "offered"})

    chain_repo = _make_chain_repo({"id": "q-1", "description": "Find the stolen goods"})
    adapter = QuestChainOfferAdapter(offer_service=mock_offer_service, chain_repo=chain_repo)

    result = await adapter.offer_quest(next_quest_id="q-1", player_id="player-1")

    assert result["status"] == "offered"
    mock_offer_service.offer_quest.assert_awaited_once()
    call_kwargs = mock_offer_service.offer_quest.call_args.kwargs
    assert call_kwargs["quest_id"] == "q-1"
    assert call_kwargs["player_id"] == "player-1"
    assert call_kwargs["title"] == "Find the stolen goods"
    assert call_kwargs["objectives"] == []
    assert call_kwargs["item_rewards"] == []
    assert call_kwargs["currency_reward"] is None


@pytest.mark.asyncio
async def test_offer_quest_idempotency_key_is_deterministic() -> None:
    """Same quest_id + player_id must produce the same idempotency_key across calls."""
    mock_offer_service = MagicMock()
    mock_offer_service.offer_quest = AsyncMock(return_value={"status": "offered"})
    chain_repo = _make_chain_repo({"id": "q-2", "description": "Patrol route"})

    adapter = QuestChainOfferAdapter(offer_service=mock_offer_service, chain_repo=chain_repo)

    await adapter.offer_quest(next_quest_id="q-2", player_id="p-1")
    await adapter.offer_quest(next_quest_id="q-2", player_id="p-1")

    calls = mock_offer_service.offer_quest.call_args_list
    key_0 = calls[0].kwargs["meta"].idempotency_key
    key_1 = calls[1].kwargs["meta"].idempotency_key
    assert key_0 == key_1, "idempotency_key must be deterministic for the same inputs"


@pytest.mark.asyncio
async def test_offer_quest_raises_when_quest_not_found() -> None:
    """Adapter must raise QuestTransitionError when the Quest node does not exist."""
    from npc_engine.utils.errors import QuestTransitionError

    mock_offer_service = MagicMock()
    chain_repo = _make_chain_repo(None)

    adapter = QuestChainOfferAdapter(offer_service=mock_offer_service, chain_repo=chain_repo)

    with pytest.raises(QuestTransitionError):
        await adapter.offer_quest(next_quest_id="ghost-quest", player_id="player-1")
