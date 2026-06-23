"""Unit tests for Neo4jMilitaryRepository (DEC-122 / SEV-24 graph repository seam)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.repositories.military_repository import Neo4jMilitaryRepository

_MOD = "npc_engine.graph.repositories.military_repository"


class _FakeGraphDB:
    def __init__(self, session: Any) -> None:
        self._session = session
        self.connect_calls = 0

    async def connect(self) -> None:
        self.connect_calls += 1

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[Any]:
        yield self._session


@pytest.mark.asyncio
async def test_get_armies_in_conflict_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMilitaryRepository(db)  # type: ignore[arg-type]
    rows = [{"location_id": "loc-1"}]

    with patch(f"{_MOD}.get_armies_in_conflict", new=AsyncMock(return_value=rows)) as mock_fn:
        result = await repo.get_armies_in_conflict()

    assert result == rows
    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_get_army_at_location_delegates_positionally():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMilitaryRepository(db)  # type: ignore[arg-type]
    rows = [{"army_id": "a1"}]

    with patch(f"{_MOD}.get_army_at_location", new=AsyncMock(return_value=rows)) as mock_fn:
        result = await repo.get_army_at_location(location_id="loc-1")

    assert result == rows
    mock_fn.assert_awaited_once_with(session, "loc-1")


@pytest.mark.asyncio
async def test_get_faction_resource_nodes_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMilitaryRepository(db)  # type: ignore[arg-type]
    rows = [{"faction_id": "fa"}]

    with patch(f"{_MOD}.get_faction_resource_nodes", new=AsyncMock(return_value=rows)) as mock_fn:
        result = await repo.get_faction_resource_nodes()

    assert result == rows
    mock_fn.assert_awaited_once_with(session)


@pytest.mark.asyncio
async def test_set_army_strength_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMilitaryRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.set_army_strength", new=AsyncMock()) as mock_fn:
        await repo.set_army_strength(army_id="a1", strength=42)

    mock_fn.assert_awaited_once_with(session, army_id="a1", strength=42)


@pytest.mark.asyncio
async def test_set_controls_location_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMilitaryRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.set_controls_location", new=AsyncMock()) as mock_fn:
        await repo.set_controls_location(
            faction_id="fa", location_id="loc-1", control_strength=100, contested_by=None
        )

    mock_fn.assert_awaited_once_with(
        session, faction_id="fa", location_id="loc-1", control_strength=100, contested_by=None
    )


@pytest.mark.asyncio
async def test_remove_controls_location_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMilitaryRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.remove_controls_location", new=AsyncMock()) as mock_fn:
        await repo.remove_controls_location(faction_id="fb", location_id="loc-1")

    mock_fn.assert_awaited_once_with(session, faction_id="fb", location_id="loc-1")


@pytest.mark.asyncio
async def test_emit_battle_event_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMilitaryRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.emit_battle_event", new=AsyncMock()) as mock_fn:
        await repo.emit_battle_event(
            event_id="e1",
            summary="s",
            severity=80,
            location_id="loc-1",
            occurred_at="2026-01-01T00:00:00+00:00",
            tick_id=5,
            winner_faction_id="fa",
        )

    assert db.connect_calls == 1
    mock_fn.assert_awaited_once_with(
        session,
        event_id="e1",
        summary="s",
        severity=80,
        location_id="loc-1",
        occurred_at="2026-01-01T00:00:00+00:00",
        tick_id=5,
        winner_faction_id="fa",
    )


@pytest.mark.asyncio
async def test_add_faction_treasury_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMilitaryRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.add_faction_treasury", new=AsyncMock()) as mock_fn:
        await repo.add_faction_treasury(faction_id="fa", amount=30)

    mock_fn.assert_awaited_once_with(session, faction_id="fa", amount=30)


@pytest.mark.asyncio
async def test_set_resource_depletion_delegates():
    session = object()
    db = _FakeGraphDB(session)
    repo = Neo4jMilitaryRepository(db)  # type: ignore[arg-type]

    with patch(f"{_MOD}.set_resource_depletion", new=AsyncMock()) as mock_fn:
        await repo.set_resource_depletion(resource_node_id="res-1", depletion=9)

    mock_fn.assert_awaited_once_with(session, resource_node_id="res-1", depletion=9)
