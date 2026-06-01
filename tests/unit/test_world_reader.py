"""
test_world_reader.py - Unit tests for world state reader coercion behavior.

Does NOT: connect to a real Neo4j instance.

Dependencies injected: in-memory session/result stubs.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import cast

import pytest
from neo4j import AsyncSession

from npc_engine.world.world_reader import get_world_state


@dataclass
class _ResultStub:
    record: dict | None

    async def single(self):
        return self.record

    async def consume(self) -> None:
        pass


class _SessionStub:
    def __init__(self, record: dict | None):
        self._record = record

    async def run(self, query: str, **params):
        return _ResultStub(record=self._record)


class _Neo4jDateTimeStub:
    def __init__(self, native_dt: datetime):
        self._native_dt = native_dt

    def to_native(self) -> datetime:
        return self._native_dt


@pytest.mark.asyncio
async def test_get_world_state_coerces_neo4j_temporal_fields() -> None:
    """Reader should convert Neo4j datetime-like values before Pydantic validation."""

    updated = datetime(2026, 4, 18, 9, 27, 2, tzinfo=timezone.utc)
    graph_updated = datetime(2026, 4, 18, 9, 27, 2, 27000, tzinfo=timezone.utc)
    session = _SessionStub(
        record={
            "world": {
                "id": "world",
                "epoch": "age_of_peace",
                "faction_standings": "{\"manual\": 10}",
                "active_conditions": "[\"manual_test\"]",
                "weather": "storm",
                "last_updated_at": _Neo4jDateTimeStub(updated),
                "last_graph_updated_at": _Neo4jDateTimeStub(graph_updated),
            }
        }
    )

    world_state = await get_world_state(session=cast(AsyncSession, session))

    assert world_state.last_updated_at == updated
    assert world_state.last_graph_updated_at == graph_updated
    assert world_state.faction_standings == {"manual": 10}
    assert world_state.active_conditions == ["manual_test"]


@pytest.mark.asyncio
async def test_get_world_state_accepts_native_collections_without_json_parse() -> None:
    """Reader should keep already-native list/dict payloads unchanged."""

    session = _SessionStub(
        record={
            "world": {
                "id": "world",
                "faction_standings": {"manual": 10},
                "active_conditions": ["manual_test"],
                "weather": "clear",
            }
        }
    )

    world_state = await get_world_state(session=cast(AsyncSession, session))

    assert world_state.faction_standings == {"manual": 10}
    assert world_state.active_conditions == ["manual_test"]


@pytest.mark.asyncio
async def test_get_world_state_missing_node_returns_default_with_requested_id() -> None:
    """When the world_state node is absent, returned WorldState id must match the requested world_id."""

    session = _SessionStub(record=None)
    world_state = await get_world_state(session=cast(AsyncSession, session), world_id="world_demo")

    assert world_state.id == "world_demo"


@pytest.mark.asyncio
async def test_get_world_state_two_worlds_are_independent() -> None:
    """Requesting different world_ids returns data from the correct node each time."""

    demo_record = {"world": {"id": "world_demo", "epoch": "war", "active_conditions": '["northern_war"]', "faction_standings": "{}"}}
    village_record = {"world": {"id": "world_village", "epoch": "age_of_peace", "active_conditions": '["crop_blight"]', "faction_standings": "{}"}}

    class _MultiWorldSession:
        """Returns the matching record based on the world_id query parameter."""

        def __init__(self) -> None:
            self._records = {"world_demo": demo_record, "world_village": village_record}

        async def run(self, query: str, world_id: str = "world", **params):
            return _ResultStub(record=self._records.get(world_id))

    session = _MultiWorldSession()
    demo = await get_world_state(session=cast(AsyncSession, session), world_id="world_demo")
    village = await get_world_state(session=cast(AsyncSession, session), world_id="world_village")

    assert demo.epoch == "war"
    assert "northern_war" in demo.active_conditions
    assert village.epoch == "age_of_peace"
    assert "crop_blight" in village.active_conditions
