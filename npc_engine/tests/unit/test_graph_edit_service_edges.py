"""
test_graph_edit_service_edges.py - Unit tests for graph edge operations in GraphEditService.

Does NOT: run against a live Neo4j instance.

Dependencies injected: None.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import cast

import pytest
pytest.importorskip("neo4j")
from neo4j import AsyncSession

from api.schemas import KnowsAboutEdgeBody, MutationMeta, RelatesToEdgeBody, WorldStatePatchBody
from api.schemas import CharacterPatchBody
from graph.graph_edit_service import GraphEditService
from graph.node_schemas import EventNode
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


@pytest.mark.asyncio
async def test_upsert_event_serializes_provenance_for_neo4j_properties() -> None:
    """Event upsert should serialize provenance maps before writing properties."""

    session = _SessionStub(records=[None])
    schema = SchemaConfig(schema_version="1.0", core_types={}, enum_extensions=EnumExtensions())
    service = GraphEditService(session=cast(AsyncSession, session), schema=schema)

    event = EventNode(
        id="event-1",
        summary="Manual event",
        severity=25,
        location_id="loc-1",
        occurred_at=datetime.now(timezone.utc),
        tick_id=1,
        participants=["npc-1"],
        event_type="crime",
        provenance={"request_id": "req-1", "actor_id": "actor-1"},
    )

    await service.upsert_event(event=event)

    _, params = session.calls[0]
    assert isinstance(params["properties"]["provenance"], str)
    assert json.loads(params["properties"]["provenance"]) == {
        "request_id": "req-1",
        "actor_id": "actor-1",
    }


@pytest.mark.asyncio
async def test_patch_world_state_serializes_collection_fields_as_json_strings() -> None:
    """World state patch should serialize map/list fields to JSON string properties."""

    session = _SessionStub(
        records=[
            {
                "node": {
                    "id": "world",
                    "faction_standings": "{\"manual\": 10}",
                    "active_conditions": "[\"manual_test\"]",
                    "weather": "storm",
                }
            }
        ]
    )
    schema = SchemaConfig(schema_version="1.0", core_types={}, enum_extensions=EnumExtensions())
    service = GraphEditService(session=cast(AsyncSession, session), schema=schema)

    body = WorldStatePatchBody(
        faction_standings={"manual": 10},
        active_conditions=["manual_test"],
        weather="storm",
        meta=MutationMeta(request_id="req-1", actor_id="actor-1", reason="manual_test"),
    )

    await service.patch_world_state(body=body)

    _, params = session.calls[0]
    assert params["set_fields"]["faction_standings"] == "{\"manual\": 10}"
    assert params["set_fields"]["active_conditions"] == "[\"manual_test\"]"


@pytest.mark.asyncio
async def test_patch_character_merges_extension_fields_and_excludes_meta() -> None:
    """Character patch should merge extension fields while excluding meta payload from set_fields."""

    session = _SessionStub(records=[{"node": {"id": "c1", "nickname": "Ash", "name": "Aldric"}}])
    schema = SchemaConfig(schema_version="1.0", core_types={}, enum_extensions=EnumExtensions())
    service = GraphEditService(session=cast(AsyncSession, session), schema=schema)

    body = CharacterPatchBody(
        name="Aldric",
        extension_fields={"nickname": "Ash"},
        meta=MutationMeta(request_id="req-1", actor_id="actor-1", reason="manual_test"),
    )

    await service.patch_character(character_id="c1", body=body)

    _, params = session.calls[0]
    assert params["set_fields"]["name"] == "Aldric"
    assert params["set_fields"]["nickname"] == "Ash"
    assert "meta" not in params["set_fields"]
    assert "extension_fields" not in params["set_fields"]
