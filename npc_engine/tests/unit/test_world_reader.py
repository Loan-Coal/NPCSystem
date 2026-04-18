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

from world.world_reader import get_world_state


@dataclass
class _ResultStub:
    record: dict | None

    async def single(self):
        return self.record


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
