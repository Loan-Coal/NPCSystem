"""Unit tests for Neo4jEventRepository (SEV-24 events slice).

Covers the EventGraphPort adapter against a fake GraphDB (session-per-call seam):
each method opens one session and delegates to the matching graph function; the
atomic emit delegates to event_emission_service.emit_event_atomic.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.graph.event_emission_service import RoutineOverridePlan
from npc_engine.graph.repositories.event_repository import Neo4jEventRepository

_MOD = "npc_engine.graph.repositories.event_repository"


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
async def test_get_locations_by_tag_delegates() -> None:
    db = _FakeGraphDB(object())
    repo = Neo4jEventRepository(db)  # type: ignore[arg-type]
    with patch(f"{_MOD}.get_locations_by_tag", new=AsyncMock(return_value=["loc-1"])) as fn:
        result = await repo.get_locations_by_tag(location_tag="keep")
    assert result == ["loc-1"]
    assert db.connect_calls == 1
    fn.assert_awaited_once_with(db._session, "keep")


@pytest.mark.asyncio
async def test_get_characters_at_location_delegates() -> None:
    db = _FakeGraphDB(object())
    repo = Neo4jEventRepository(db)  # type: ignore[arg-type]
    with patch(f"{_MOD}.get_characters_at_location", new=AsyncMock(return_value=["c1"])) as fn:
        result = await repo.get_characters_at_location(location_id="loc-1")
    assert result == ["c1"]
    fn.assert_awaited_once_with(db._session, "loc-1")


@pytest.mark.asyncio
async def test_emit_event_atomic_delegates() -> None:
    db = _FakeGraphDB(object())
    repo = Neo4jEventRepository(db)  # type: ignore[arg-type]
    overrides = [RoutineOverridePlan(override_location="home", expires_at_tick=10)]
    event = object()
    with patch(f"{_MOD}.emit_event_atomic", new=AsyncMock()) as fn:
        await repo.emit_event_atomic(
            event=event,  # type: ignore[arg-type]
            event_id="evt-1",
            location_id="loc-1",
            tick_id=3,
            faction_id="guild",
            reputation_delta=-5,
            routine_overrides=overrides,
            world_condition_event_type="military",
            world_id="world",
        )
    assert db.connect_calls == 1
    fn.assert_awaited_once_with(
        db._session,
        event=event,
        event_id="evt-1",
        location_id="loc-1",
        tick_id=3,
        faction_id="guild",
        reputation_delta=-5,
        routine_overrides=overrides,
        world_condition_event_type="military",
        world_id="world",
    )


@pytest.mark.asyncio
async def test_record_witnesses_one_session_per_call() -> None:
    db = _FakeGraphDB(object())
    repo = Neo4jEventRepository(db)  # type: ignore[arg-type]
    with patch(f"{_MOD}.record_witness", new=AsyncMock()) as fn:
        await repo.record_witnesses(
            witness_ids=["w1", "w2"],
            subject_id="actor",
            event_id="evt-1",
            action_type="fight",
            tick=4,
            clarity=70,
            interpretation="brawl",
        )
    assert db.connect_calls == 1
    assert fn.await_count == 2
    assert {call.kwargs["witness_id"] for call in fn.await_args_list} == {"w1", "w2"}


@pytest.mark.asyncio
async def test_record_causation_delegates() -> None:
    db = _FakeGraphDB(object())
    repo = Neo4jEventRepository(db)  # type: ignore[arg-type]
    with patch(f"{_MOD}.record_causation", new=AsyncMock()) as fn:
        await repo.record_causation(
            effect_node_id="evt-2",
            effect_node_type="event",
            cause_event_id="evt-1",
            causation_strength=100,
            cause_type="direct",
            tick_lag=0,
        )
    fn.assert_awaited_once_with(
        db._session,
        effect_node_id="evt-2",
        effect_node_type="event",
        cause_event_id="evt-1",
        causation_strength=100,
        cause_type="direct",
        tick_lag=0,
    )
