"""Unit tests for SuccessionEngine — graph access via a mocked PoliticalGraphPort."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.succession.succession_engine import SuccessionEngine


def _make_repo(
    vacant: list[dict[str, Any]] | None = None,
    heirs: list[dict[str, Any]] | None = None,
) -> AsyncMock:
    repo = AsyncMock()
    repo.get_vacant_inheritable_titles = AsyncMock(return_value=vacant or [])
    repo.get_heirs_for_character = AsyncMock(return_value=heirs or [])
    repo.grant_title = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_vacant_title_triggers_succession():
    """When a title is vacant and an heir exists, grant_title is called."""
    vacant = [{"id": "title-duke", "name": "Duke of Ember", "faction_id": "faction-ember"}]
    heirs = [{"heir": {"id": "char-heir-01"}, "priority": 1, "legitimacy": 80}]
    repo = _make_repo(vacant=vacant, heirs=heirs)
    engine = SuccessionEngine(political_repo=repo)

    result = await engine.run_tick(tick_id=10)

    assert result["successions"] == 1
    repo.grant_title.assert_awaited_once_with(
        character_id="char-heir-01", title_id="title-duke", tick=10
    )


@pytest.mark.asyncio
async def test_no_succession_when_no_heirs():
    vacant = [{"id": "title-duke", "name": "Duke", "faction_id": "faction-ember"}]
    repo = _make_repo(vacant=vacant, heirs=[])
    engine = SuccessionEngine(political_repo=repo)

    result = await engine.run_tick(tick_id=10)

    assert result["successions"] == 0
    repo.grant_title.assert_not_called()


@pytest.mark.asyncio
async def test_no_succession_when_no_vacant_titles():
    repo = _make_repo(vacant=[])
    engine = SuccessionEngine(political_repo=repo)

    result = await engine.run_tick(tick_id=5)

    assert result["successions"] == 0
    repo.grant_title.assert_not_called()


@pytest.mark.asyncio
async def test_highest_priority_heir_wins():
    """The first heir in the returned (priority-ordered) list is granted the title."""
    vacant = [{"id": "title-king", "name": "King", "faction_id": "faction-crown"}]
    heirs = [
        {"heir": {"id": "char-first-heir"}, "priority": 1, "legitimacy": 90},
        {"heir": {"id": "char-second-heir"}, "priority": 2, "legitimacy": 85},
    ]
    repo = _make_repo(vacant=vacant, heirs=heirs)
    engine = SuccessionEngine(political_repo=repo)

    result = await engine.run_tick(tick_id=20)

    assert result["successions"] == 1
    assert repo.grant_title.call_args.kwargs["character_id"] == "char-first-heir"


@pytest.mark.asyncio
async def test_scheduler_session_kwarg_is_ignored():
    vacant = [{"id": "t", "name": "T", "faction_id": "f"}]
    heirs = [{"heir": {"id": "h"}, "priority": 1, "legitimacy": 50}]
    repo = _make_repo(vacant=vacant, heirs=heirs)
    engine = SuccessionEngine(political_repo=repo)

    result = await engine.run_tick(session=object(), tick_id=3)

    assert result["successions"] == 1
