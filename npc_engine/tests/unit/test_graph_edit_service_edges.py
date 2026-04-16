"""
test_graph_edit_service_edges.py - Unit tests for graph edge operations in GraphEditService.

Does NOT: run against a live Neo4j instance.

Dependencies injected: None.
"""

from dataclasses import dataclass
from typing import cast

import pytest
from neo4j import AsyncSession

from api.schemas import KnowsAboutEdgeBody, MutationMeta, RelatesToEdgeBody
from graph.graph_edit_service import GraphEditService
from schema.schema_models import EnumExtensions, SchemaConfig
from utils.errors import NodeNotFoundError


@dataclass
class _ResultStub:
    record: dict | None

    async def single(self):
        return self.record


class _SessionStub:
    def __init__(self, records: list[dict | None]):
        self._records = list(records)
        self.calls: list[tuple[str, dict]] = []

    async def run(self, query: str, **params):
        self.calls.append((query, params))
        record = self._records.pop(0) if self._records else None
        return _ResultStub(record=record)


@pytest.mark.asyncio
async def test_upsert_relates_to_edge_enforces_match_referential_integrity() -> None:
    """RELATES_TO edge upsert query should match both endpoint nodes before merge."""

    session = _SessionStub(records=[{"trust": 10, "fear": 20, "affection": 30}])
    schema = SchemaConfig(schema_version="1.0", core_types={}, enum_extensions=EnumExtensions())
    service = GraphEditService(session=cast(AsyncSession, session), schema=schema)

    body = RelatesToEdgeBody(
        src_id="c1",
        dst_id="c2",
        trust=10,
        fear=20,
        affection=30,
        meta=MutationMeta(request_id="r1", actor_id="a1", reason="seed"),
    )

    await service.upsert_relates_to_edge(body=body)

    query, _ = session.calls[0]
    assert "MATCH (a:Character {id: $src_id})" in query
    assert "MATCH (b:Character {id: $dst_id})" in query
    assert "MERGE (a)-[r:RELATES_TO]->(b)" in query


@pytest.mark.asyncio
async def test_delete_knows_about_edge_returns_false_when_missing() -> None:
    """Delete should return False when target edge does not exist."""

    session = _SessionStub(records=[None])
    schema = SchemaConfig(schema_version="1.0", core_types={}, enum_extensions=EnumExtensions())
    service = GraphEditService(session=cast(AsyncSession, session), schema=schema)

    deleted = await service.delete_knows_about_edge(character_id="c1", event_id="e1")

    assert deleted is False


@pytest.mark.asyncio
async def test_upsert_knows_about_edge_raises_when_nodes_missing() -> None:
    """KNOWS_ABOUT upsert should raise if either endpoint node cannot be matched."""

    session = _SessionStub(records=[None])
    schema = SchemaConfig(schema_version="1.0", core_types={}, enum_extensions=EnumExtensions())
    service = GraphEditService(session=cast(AsyncSession, session), schema=schema)

    body = KnowsAboutEdgeBody(
        character_id="c1",
        event_id="e1",
        knowledge_state="knows",
        learned_at_tick=1,
        meta=MutationMeta(request_id="r1", actor_id="a1", reason="seed"),
    )

    with pytest.raises(NodeNotFoundError):
        await service.upsert_knows_about_edge(body=body)
