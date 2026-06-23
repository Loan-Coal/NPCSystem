"""
test_generic_graph_service.py - Unit tests for registry-driven generic graph service.

Does NOT: run against a live Neo4j instance.

Dependencies injected: tmp_path fixture.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
pytest.importorskip("neo4j")
from neo4j import AsyncSession

from npc_engine.graph.generic.generic_graph_service import GenericGraphService
from npc_engine.schema.schema_loader import load_game_schema
from npc_engine.type_registry.registry import build_type_registry
from npc_engine.utils.errors import NodeNotFoundError


@dataclass
class _ResultStub:
    record: dict[str, Any] | None

    async def single(self) -> dict[str, Any] | None:
        return self.record

    async def consume(self) -> None:
        pass


class _SessionStub:
    def __init__(self, records: list[dict[str, Any] | None]):
        self._records = list(records)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def run(self, query: str, **params: Any) -> _ResultStub:
        self.calls.append((query, params))
        record = self._records.pop(0) if self._records else None
        return _ResultStub(record=record)


@pytest.fixture()
def registry_fixture(tmp_path: Path):
    schema_path = tmp_path / "game_schema.yaml"
    schema_path.write_text(
        """
schema_version: "1.0"
core_types: {}
enum_extensions:
  event_type: []
  participation_role: []
""".strip(),
        encoding="utf-8",
    )
    base_schema = load_game_schema(schema_path=str(schema_path))
    return build_type_registry(base_schema=base_schema, extension_sources=())


@pytest.mark.asyncio
async def test_upsert_edge_enforces_endpoint_match_before_merge(registry_fixture) -> None:
    """Edge upsert query should match source and destination nodes before MERGE."""

    session = _SessionStub(records=[{"edge": {"trust": 10, "fear": 20, "affection": 30}, "src_id": "c1", "dst_id": "c2"}])
    service = GenericGraphService(session=cast(AsyncSession, session), registry=registry_fixture)

    await service.upsert_edge(
        edge_type="RELATES_TO",
        src_id="c1",
        dst_id="c2",
        payload={
            "trust": 10,
            "fear": 20,
            "affection": 30,
            "interaction_count": 0,
            "last_updated_at": "2026-05-01T00:00:00Z",
            "relevance_score": 0.5,
        },
    )

    query, _ = session.calls[0]
    assert "MATCH (src:`Character` {id: $src_id})" in query
    assert "MATCH (dst:`Character` {id: $dst_id})" in query
    assert "MERGE (src)-[e:`RELATES_TO`]->(dst)" in query


@pytest.mark.asyncio
async def test_delete_edge_returns_false_when_missing(registry_fixture) -> None:
    """Delete should return False when target edge does not exist."""

    session = _SessionStub(records=[None])
    service = GenericGraphService(session=cast(AsyncSession, session), registry=registry_fixture)

    deleted = await service.delete_edge(edge_type="RELATES_TO", src_id="c1", dst_id="c2")

    assert deleted is False


@pytest.mark.asyncio
async def test_upsert_edge_raises_when_nodes_missing(registry_fixture) -> None:
    """Upsert should raise when endpoint nodes cannot be matched."""

    session = _SessionStub(records=[None])
    service = GenericGraphService(session=cast(AsyncSession, session), registry=registry_fixture)

    with pytest.raises(NodeNotFoundError):
        await service.upsert_edge(
            edge_type="RELATES_TO",
            src_id="c1",
            dst_id="c2",
            payload={
                "trust": 10,
                "fear": 20,
                "affection": 30,
                "interaction_count": 0,
                "last_updated_at": "2026-05-01T00:00:00Z",
                "relevance_score": 0.5,
            },
        )


@pytest.mark.asyncio
async def test_upsert_node_serializes_dict_fields_for_storage(registry_fixture) -> None:
    """Node upsert should encode dict properties as JSON strings for persistence."""

    session = _SessionStub(records=[{"node": {"id": "world", "epoch": "dawn", "faction_standings": "{\"guild\": 10}", "active_conditions": ["rain"], "weather": "storm"}}])
    service = GenericGraphService(session=cast(AsyncSession, session), registry=registry_fixture)

    await service.upsert_node(
        node_type="world_state",
        payload={
            "id": "world",
            "epoch": "dawn",
            "faction_standings": {"guild": 10},
            "active_conditions": ["rain"],
            "weather": "storm",
            "time_of_day": "morning",
            "last_updated_at": "2026-05-01T00:00:00Z",
            "last_graph_updated_at": "2026-05-01T00:00:00Z",
        },
    )

    _, params = session.calls[0]
    assert params["properties"]["faction_standings"] == "{\"guild\": 10}"
