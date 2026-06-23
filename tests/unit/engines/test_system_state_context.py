"""
test_system_state_context.py — Unit tests for SystemStateContext and resolve_system_state.

Does NOT: open real Neo4j sessions or call live services.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.dialogue.system_state_context import (
    SystemStateContext,
    resolve_system_state,
)


# ---------------------------------------------------------------------------
# SystemStateContext model tests
# ---------------------------------------------------------------------------

def test_system_state_context_defaults() -> None:
    ctx = SystemStateContext()
    assert ctx.npc_can_trade is False
    assert ctx.npc_item_count == 0
    assert ctx.player_quest_status is None


def test_system_state_context_with_items() -> None:
    ctx = SystemStateContext(npc_can_trade=True, npc_item_count=3)
    assert ctx.npc_can_trade is True
    assert ctx.npc_item_count == 3


def test_system_state_context_immutable() -> None:
    ctx = SystemStateContext(npc_can_trade=True, npc_item_count=2)
    with pytest.raises(Exception):
        ctx.npc_can_trade = False  # type: ignore[misc]


def test_system_state_context_serializes_to_json() -> None:
    ctx = SystemStateContext(npc_can_trade=False, npc_item_count=0, player_quest_status="in_progress")
    data = ctx.model_dump()
    assert data["npc_can_trade"] is False
    assert data["player_quest_status"] == "in_progress"


# ---------------------------------------------------------------------------
# resolve_system_state integration-style unit tests (mocked graph)
# ---------------------------------------------------------------------------

def _make_session(items: list[Any], quest: dict[str, Any] | None) -> AsyncMock:
    """Build a mock AsyncSession where item/quest queries return the given data."""
    session = AsyncMock()
    return session


@pytest.fixture()
def fake_settings() -> MagicMock:
    return MagicMock()


@pytest.mark.asyncio
async def test_resolve_system_state_no_items_no_quest(fake_settings: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "npc_engine.graph.economy.item_queries.get_items_for_character",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "npc_engine.graph.quest.quest_queries.get_active_quest_for_player",
        AsyncMock(return_value=None),
    )
    session = AsyncMock()
    result = await resolve_system_state(session=session, npc_id="npc1", player_id="player1", settings=fake_settings)
    assert result.npc_can_trade is False
    assert result.npc_item_count == 0
    assert result.player_quest_status is None


@pytest.mark.asyncio
async def test_resolve_system_state_with_items(fake_settings: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "npc_engine.graph.economy.item_queries.get_items_for_character",
        AsyncMock(return_value=[{"id": "sword"}, {"id": "shield"}]),
    )
    monkeypatch.setattr(
        "npc_engine.graph.quest.quest_queries.get_active_quest_for_player",
        AsyncMock(return_value=None),
    )
    session = AsyncMock()
    result = await resolve_system_state(session=session, npc_id="npc1", player_id="player1", settings=fake_settings)
    assert result.npc_can_trade is True
    assert result.npc_item_count == 2


@pytest.mark.asyncio
async def test_resolve_system_state_with_active_quest(fake_settings: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "npc_engine.graph.economy.item_queries.get_items_for_character",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "npc_engine.graph.quest.quest_queries.get_active_quest_for_player",
        AsyncMock(return_value={"quest_id": "q1", "status": "in_progress"}),
    )
    session = AsyncMock()
    result = await resolve_system_state(session=session, npc_id="npc1", player_id="player1", settings=fake_settings)
    assert result.player_quest_status == "in_progress"


@pytest.mark.asyncio
async def test_resolve_system_state_no_player_skips_quest(fake_settings: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    items_mock = AsyncMock(return_value=[])
    quest_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "npc_engine.graph.economy.item_queries.get_items_for_character",
        items_mock,
    )
    monkeypatch.setattr(
        "npc_engine.graph.quest.quest_queries.get_active_quest_for_player",
        quest_mock,
    )
    session = AsyncMock()
    result = await resolve_system_state(session=session, npc_id="npc1", player_id=None, settings=fake_settings)
    assert result.player_quest_status is None
    quest_mock.assert_not_awaited()
