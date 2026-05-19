"""Unit tests for AgendaEngine (Phase 7.2 Political Simulation)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.engines.agenda.agenda_engine import AgendaEngine


@pytest.fixture
def engine() -> AgendaEngine:
    return AgendaEngine()


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


# ---------------------------------------------------------------------------
# Agenda resolution logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agenda_passes_when_support_exceeds_opposition(engine, session):
    """An agenda past its deadline is marked 'passed' when support weight > oppose weight."""
    expired_agenda = {
        "id": "agenda-trade-reform",
        "description": "Open the northern trade routes",
        "proposed_by_faction_id": "faction-merchants",
        "status": "open",
        "deadline_tick": 10,
    }
    votes = {
        "supports": [{"character": {"id": "char-a"}, "weight": 80}],
        "opposes": [{"character": {"id": "char-b"}, "weight": 30}],
    }

    with (
        patch(
            "npc_engine.engines.agenda.agenda_engine.get_expired_open_agendas",
            new=AsyncMock(return_value=[expired_agenda]),
        ),
        patch(
            "npc_engine.engines.agenda.agenda_engine.get_agenda_votes",
            new=AsyncMock(return_value=votes),
        ),
        patch(
            "npc_engine.engines.agenda.agenda_engine.set_agenda_status",
            new=AsyncMock(),
        ) as mock_set,
    ):
        result = await engine.run_tick(session, tick_id=10)

    assert result["resolved"] == 1
    assert result["passed"] == 1
    assert result["failed"] == 0
    mock_set.assert_called_once_with(session, agenda_id="agenda-trade-reform", status="passed")


@pytest.mark.asyncio
async def test_agenda_fails_when_opposition_equals_support(engine, session):
    """An agenda is marked 'failed' when oppose weight equals support weight (tie → fail)."""
    expired_agenda = {
        "id": "agenda-war",
        "description": "Declare war on the southern kingdom",
        "proposed_by_faction_id": "faction-hawks",
        "status": "open",
        "deadline_tick": 5,
    }
    votes = {
        "supports": [{"character": {"id": "char-hawk"}, "weight": 50}],
        "opposes": [{"character": {"id": "char-dove"}, "weight": 50}],
    }

    with (
        patch(
            "npc_engine.engines.agenda.agenda_engine.get_expired_open_agendas",
            new=AsyncMock(return_value=[expired_agenda]),
        ),
        patch(
            "npc_engine.engines.agenda.agenda_engine.get_agenda_votes",
            new=AsyncMock(return_value=votes),
        ),
        patch(
            "npc_engine.engines.agenda.agenda_engine.set_agenda_status",
            new=AsyncMock(),
        ) as mock_set,
    ):
        result = await engine.run_tick(session, tick_id=5)

    assert result["failed"] == 1
    mock_set.assert_called_once_with(session, agenda_id="agenda-war", status="failed")


@pytest.mark.asyncio
async def test_agenda_fails_when_no_votes(engine, session):
    """An agenda with no votes at all is marked 'failed' (no consensus = failure)."""
    expired_agenda = {
        "id": "agenda-census",
        "description": "Conduct a kingdom census",
        "proposed_by_faction_id": "faction-scribes",
        "status": "open",
        "deadline_tick": 3,
    }
    votes = {"supports": [], "opposes": []}

    with (
        patch(
            "npc_engine.engines.agenda.agenda_engine.get_expired_open_agendas",
            new=AsyncMock(return_value=[expired_agenda]),
        ),
        patch(
            "npc_engine.engines.agenda.agenda_engine.get_agenda_votes",
            new=AsyncMock(return_value=votes),
        ),
        patch(
            "npc_engine.engines.agenda.agenda_engine.set_agenda_status",
            new=AsyncMock(),
        ) as mock_set,
    ):
        result = await engine.run_tick(session, tick_id=3)

    assert result["failed"] == 1
    mock_set.assert_called_once_with(session, agenda_id="agenda-census", status="failed")


@pytest.mark.asyncio
async def test_agendas_before_deadline_are_not_resolved(engine, session):
    """Agendas whose deadline has not passed are not touched."""
    with (
        patch(
            "npc_engine.engines.agenda.agenda_engine.get_expired_open_agendas",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.agenda.agenda_engine.set_agenda_status",
            new=AsyncMock(),
        ) as mock_set,
    ):
        result = await engine.run_tick(session, tick_id=1)

    assert result["resolved"] == 0
    mock_set.assert_not_called()


@pytest.mark.asyncio
async def test_multiple_agendas_resolved_independently(engine, session):
    """Two expired agendas are each resolved according to their own vote tally."""
    agendas = [
        {"id": "a-1", "description": "Agenda 1", "proposed_by_faction_id": "f-1", "status": "open", "deadline_tick": 5},
        {"id": "a-2", "description": "Agenda 2", "proposed_by_faction_id": "f-2", "status": "open", "deadline_tick": 5},
    ]
    votes_map = {
        "a-1": {"supports": [{"character": {"id": "c"}, "weight": 100}], "opposes": []},
        "a-2": {"supports": [], "opposes": [{"character": {"id": "d"}, "weight": 60}]},
    }

    async def _get_votes(session, agenda_id):
        return votes_map[agenda_id]

    with (
        patch(
            "npc_engine.engines.agenda.agenda_engine.get_expired_open_agendas",
            new=AsyncMock(return_value=agendas),
        ),
        patch(
            "npc_engine.engines.agenda.agenda_engine.get_agenda_votes",
            new=_get_votes,
        ),
        patch(
            "npc_engine.engines.agenda.agenda_engine.set_agenda_status",
            new=AsyncMock(),
        ) as mock_set,
    ):
        result = await engine.run_tick(session, tick_id=5)

    assert result["resolved"] == 2
    assert result["passed"] == 1
    assert result["failed"] == 1
