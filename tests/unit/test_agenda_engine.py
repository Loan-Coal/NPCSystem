"""Unit tests for AgendaEngine — graph access via a mocked PoliticalGraphPort."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.agenda.agenda_engine import AgendaEngine


def _make_repo(
    expired: list[dict[str, Any]] | None = None,
    votes: dict[str, Any] | None = None,
) -> AsyncMock:
    repo = AsyncMock()
    repo.get_expired_open_agendas = AsyncMock(return_value=expired or [])
    repo.get_agenda_votes = AsyncMock(return_value=votes or {"supports": [], "opposes": []})
    repo.set_agenda_status = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_agenda_passes_when_support_exceeds_opposition():
    agenda = {"id": "agenda-trade-reform", "description": "Open trade routes"}
    votes = {
        "supports": [{"character": {"id": "char-a"}, "weight": 80}],
        "opposes": [{"character": {"id": "char-b"}, "weight": 30}],
    }
    repo = _make_repo(expired=[agenda], votes=votes)
    engine = AgendaEngine(political_repo=repo)

    result = await engine.run_tick(tick_id=10)

    assert result == {"resolved": 1, "passed": 1, "failed": 0}
    repo.set_agenda_status.assert_awaited_once_with(agenda_id="agenda-trade-reform", status="passed")


@pytest.mark.asyncio
async def test_agenda_fails_when_opposition_equals_support():
    agenda = {"id": "agenda-war", "description": "Declare war"}
    votes = {
        "supports": [{"character": {"id": "char-hawk"}, "weight": 50}],
        "opposes": [{"character": {"id": "char-dove"}, "weight": 50}],
    }
    repo = _make_repo(expired=[agenda], votes=votes)
    engine = AgendaEngine(political_repo=repo)

    result = await engine.run_tick(tick_id=5)

    assert result["failed"] == 1
    repo.set_agenda_status.assert_awaited_once_with(agenda_id="agenda-war", status="failed")


@pytest.mark.asyncio
async def test_agenda_fails_when_no_votes():
    agenda = {"id": "agenda-census", "description": "Census"}
    repo = _make_repo(expired=[agenda], votes={"supports": [], "opposes": []})
    engine = AgendaEngine(political_repo=repo)

    result = await engine.run_tick(tick_id=3)

    assert result["failed"] == 1
    repo.set_agenda_status.assert_awaited_once_with(agenda_id="agenda-census", status="failed")


@pytest.mark.asyncio
async def test_agendas_before_deadline_are_not_resolved():
    repo = _make_repo(expired=[])
    engine = AgendaEngine(political_repo=repo)

    result = await engine.run_tick(tick_id=1)

    assert result["resolved"] == 0
    repo.set_agenda_status.assert_not_called()


@pytest.mark.asyncio
async def test_scheduler_session_kwarg_is_ignored():
    agenda = {"id": "a", "description": "A"}
    repo = _make_repo(expired=[agenda], votes={"supports": [{"weight": 10}], "opposes": []})
    engine = AgendaEngine(political_repo=repo)

    result = await engine.run_tick(session=object(), tick_id=2)

    assert result["passed"] == 1


@pytest.mark.asyncio
async def test_multiple_agendas_resolved_independently():
    agendas = [
        {"id": "a-1", "description": "Agenda 1"},
        {"id": "a-2", "description": "Agenda 2"},
    ]
    votes_map = {
        "a-1": {"supports": [{"character": {"id": "c"}, "weight": 100}], "opposes": []},
        "a-2": {"supports": [], "opposes": [{"character": {"id": "d"}, "weight": 60}]},
    }
    repo = _make_repo(expired=agendas)
    repo.get_agenda_votes = AsyncMock(side_effect=lambda *, agenda_id: votes_map[agenda_id])
    engine = AgendaEngine(political_repo=repo)

    result = await engine.run_tick(tick_id=5)

    assert result == {"resolved": 2, "passed": 1, "failed": 1}
