"""Unit tests for SuccessionEngine (Phase 7.2 Political Simulation)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.engines.succession.succession_engine import SuccessionEngine


@pytest.fixture
def engine() -> SuccessionEngine:
    return SuccessionEngine()


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


# ---------------------------------------------------------------------------
# Vacant title → heir granted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vacant_title_triggers_succession(engine, session):
    """When a title is vacant and an heir exists, grant_title is called."""
    vacant_title = {"id": "title-duke", "name": "Duke of Ember", "faction_id": "faction-ember", "is_inheritable": True}
    heir = {"heir": {"id": "char-heir-01"}, "priority": 1, "legitimacy": 80}

    with (
        patch(
            "npc_engine.engines.succession.succession_engine.get_vacant_inheritable_titles",
            new=AsyncMock(return_value=[vacant_title]),
        ),
        patch(
            "npc_engine.engines.succession.succession_engine.get_heirs_for_character",
            new=AsyncMock(return_value=[heir]),
        ),
        patch(
            "npc_engine.engines.succession.succession_engine.grant_title",
            new=AsyncMock(),
        ) as mock_grant,
    ):
        result = await engine.run_tick(session, tick_id=10)

    assert result["successions"] == 1
    mock_grant.assert_called_once_with(
        session,
        character_id="char-heir-01",
        title_id="title-duke",
        tick=10,
    )


@pytest.mark.asyncio
async def test_no_succession_when_no_heirs(engine, session):
    """When a title is vacant but there are no heirs, no succession occurs."""
    vacant_title = {"id": "title-duke", "name": "Duke of Ember", "faction_id": "faction-ember", "is_inheritable": True}

    with (
        patch(
            "npc_engine.engines.succession.succession_engine.get_vacant_inheritable_titles",
            new=AsyncMock(return_value=[vacant_title]),
        ),
        patch(
            "npc_engine.engines.succession.succession_engine.get_heirs_for_character",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.succession.succession_engine.grant_title",
            new=AsyncMock(),
        ) as mock_grant,
    ):
        result = await engine.run_tick(session, tick_id=10)

    assert result["successions"] == 0
    mock_grant.assert_not_called()


@pytest.mark.asyncio
async def test_no_succession_when_no_vacant_titles(engine, session):
    """When there are no vacant titles, succession is a no-op."""
    with (
        patch(
            "npc_engine.engines.succession.succession_engine.get_vacant_inheritable_titles",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.succession.succession_engine.grant_title",
            new=AsyncMock(),
        ) as mock_grant,
    ):
        result = await engine.run_tick(session, tick_id=5)

    assert result["successions"] == 0
    mock_grant.assert_not_called()


@pytest.mark.asyncio
async def test_highest_priority_heir_wins(engine, session):
    """The heir with the lowest priority number is granted the title first."""
    vacant_title = {"id": "title-king", "name": "King", "faction_id": "faction-crown", "is_inheritable": True}
    heirs = [
        {"heir": {"id": "char-first-heir"}, "priority": 1, "legitimacy": 90},
        {"heir": {"id": "char-second-heir"}, "priority": 2, "legitimacy": 85},
    ]

    with (
        patch(
            "npc_engine.engines.succession.succession_engine.get_vacant_inheritable_titles",
            new=AsyncMock(return_value=[vacant_title]),
        ),
        patch(
            "npc_engine.engines.succession.succession_engine.get_heirs_for_character",
            new=AsyncMock(return_value=heirs),
        ),
        patch(
            "npc_engine.engines.succession.succession_engine.grant_title",
            new=AsyncMock(),
        ) as mock_grant,
    ):
        result = await engine.run_tick(session, tick_id=20)

    assert result["successions"] == 1
    call_kwargs = mock_grant.call_args.kwargs
    assert call_kwargs["character_id"] == "char-first-heir"
