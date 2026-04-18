"""
graph_edit_service.py - Orchestrates typed graph resource reads and mutations.

Does NOT: enforce auth scope policy.

Dependencies injected: AsyncSession, SchemaConfig.
"""

import json
from datetime import datetime, timezone
from typing import Any

from neo4j import AsyncSession

from api.schemas import (
    CharacterPatchBody,
    EventPatchBody,
    KnowsAboutEdgeBody,
    LocatedAtEdgeBody,
    LocationPatchBody,
    ParticipatedInEdgeBody,
    RelatesToEdgeBody,
    WorldStatePatchBody,
)
from graph.graph_edit_validator import ensure_no_immutable_fields, validate_extension_fields
from graph.node_schemas import CharacterNode, EventNode, LocationNode
from schema.schema_models import SchemaConfig
from utils.errors import NodeNotFoundError


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _to_json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_safe_value(item) for item in value]
    return str(value)


def _to_json_safe_node(node: dict[str, Any]) -> dict[str, Any]:
    normalized = _to_json_safe_value(node)
    if isinstance(normalized, dict):
        return normalized
    return {}


def _build_patch_set_fields(
    *,
    body: CharacterPatchBody | EventPatchBody | LocationPatchBody,
    node_type: str,
    schema: SchemaConfig,
) -> dict[str, Any]:
    """Normalize PATCH payload by removing metadata and merging validated extension fields."""

    set_payload = body.model_dump(exclude_none=True)
    extension_fields = set_payload.pop("extension_fields", None)
    set_payload.pop("meta", None)
    ensure_no_immutable_fields(node_type=node_type, set_fields=set_payload)
    validate_extension_fields(schema, node_type, extension_fields)
    return {**set_payload, **(extension_fields or {})}


def _serialize_world_state_patch(body: WorldStatePatchBody) -> dict[str, Any]:
    """Serialize world state patch payload using full-replace JSON semantics for collection fields."""

    set_payload = body.model_dump(exclude_none=True)
    set_payload.pop("extension_fields", None)
    set_payload.pop("meta", None)
    if "faction_standings" in set_payload:
        set_payload["faction_standings"] = json.dumps(set_payload["faction_standings"], sort_keys=True)
    if "active_conditions" in set_payload:
        set_payload["active_conditions"] = json.dumps(set_payload["active_conditions"])
    return set_payload


class GraphEditService:
    """Service for v1.3 graph CRUD-style operations on core resources."""

    def __init__(self, session: AsyncSession, schema: SchemaConfig):
        self._session = session
        self._schema = schema

    async def get_character(self, character_id: str) -> dict | None:
        result = await self._session.run(
            "MATCH (c:Character {id: $id}) RETURN properties(c) AS node",
            id=character_id,
        )
        record = await result.single()
        return None if record is None else _to_json_safe_node(dict(record["node"]))

    async def list_characters(self, limit: int, offset: int) -> list[dict]:
        result = await self._session.run(
            "MATCH (c:Character) RETURN properties(c) AS node ORDER BY c.id SKIP $offset LIMIT $limit",
            limit=limit,
            offset=offset,
        )
        return [_to_json_safe_node(dict(record["node"])) async for record in result]

    async def upsert_character(self, character: CharacterNode) -> None:
        payload = character.model_dump(mode="json")
        await self._session.run(
            "MERGE (c:Character {id: $id}) "
            "SET c += $properties, c.updated_at = datetime(), c.last_graph_updated_at = datetime()",
            id=character.id,
            properties=payload,
        )

    async def patch_character(self, character_id: str, body: CharacterPatchBody) -> dict:
        merged = _build_patch_set_fields(body=body, node_type="character", schema=self._schema)
        result = await self._session.run(
            "MATCH (c:Character {id: $id}) "
            "SET c += $set_fields, c.updated_at = datetime(), c.last_graph_updated_at = datetime() "
            "RETURN properties(c) AS node",
            id=character_id,
            set_fields=merged,
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type="character", node_id=character_id)
        return _to_json_safe_node(dict(record["node"]))

    async def soft_delete_character(self, character_id: str) -> None:
        result = await self._session.run(
            "MATCH (c:Character {id: $id}) "
            "SET c.is_active = false, c.updated_at = datetime(), c.last_graph_updated_at = datetime() "
            "RETURN c.id AS id",
            id=character_id,
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type="character", node_id=character_id)

    async def move_character(self, character_id: str, location_id: str) -> None:
        result = await self._session.run(
            "MATCH (c:Character {id: $character_id}) "
            "MATCH (loc:Location {id: $location_id}) "
            "OPTIONAL MATCH (c)-[old:LOCATED_AT]->(:Location) "
            "DELETE old "
            "MERGE (c)-[la:LOCATED_AT]->(loc) "
            "SET la.arrived_at = datetime(), "
            "    c.current_location_id = $location_id, "
            "    c.updated_at = datetime(), "
            "    c.last_graph_updated_at = datetime() "
            "RETURN c.id AS id",
            character_id=character_id,
            location_id=location_id,
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type="character|location", node_id=f"{character_id}:{location_id}")

    async def patch_event(self, event_id: str, body: EventPatchBody) -> dict:
        merged = _build_patch_set_fields(body=body, node_type="event", schema=self._schema)
        result = await self._session.run(
            "MATCH (e:Event {id: $id}) "
            "SET e += $set_fields, e.last_graph_updated_at = datetime() "
            "RETURN properties(e) AS node",
            id=event_id,
            set_fields=merged,
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type="event", node_id=event_id)
        return _to_json_safe_node(dict(record["node"]))

    async def get_event(self, event_id: str) -> dict | None:
        result = await self._session.run(
            "MATCH (e:Event {id: $id}) RETURN properties(e) AS node",
            id=event_id,
        )
        record = await result.single()
        return None if record is None else _to_json_safe_node(dict(record["node"]))

    async def list_events(self, limit: int, offset: int) -> list[dict]:
        result = await self._session.run(
            "MATCH (e:Event) RETURN properties(e) AS node ORDER BY e.id SKIP $offset LIMIT $limit",
            limit=limit,
            offset=offset,
        )
        return [_to_json_safe_node(dict(record["node"])) async for record in result]

    async def upsert_event(self, event: EventNode) -> None:
        payload = event.model_dump(mode="json")
        provenance = payload.get("provenance")
        if isinstance(provenance, dict):
            payload["provenance"] = json.dumps(provenance, sort_keys=True)
        await self._session.run(
            "MERGE (e:Event {id: $id}) "
            "SET e += $properties, e.last_graph_updated_at = datetime()",
            id=event.id,
            properties=payload,
        )

    async def patch_location(self, location_id: str, body: LocationPatchBody) -> dict:
        merged = _build_patch_set_fields(body=body, node_type="location", schema=self._schema)
        result = await self._session.run(
            "MATCH (loc:Location {id: $id}) "
            "SET loc += $set_fields, loc.last_graph_updated_at = datetime() "
            "RETURN properties(loc) AS node",
            id=location_id,
            set_fields=merged,
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type="location", node_id=location_id)
        return _to_json_safe_node(dict(record["node"]))

    async def get_location(self, location_id: str) -> dict | None:
        result = await self._session.run(
            "MATCH (loc:Location {id: $id}) RETURN properties(loc) AS node",
            id=location_id,
        )
        record = await result.single()
        return None if record is None else _to_json_safe_node(dict(record["node"]))

    async def list_locations(self, limit: int, offset: int) -> list[dict]:
        result = await self._session.run(
            "MATCH (loc:Location) RETURN properties(loc) AS node ORDER BY loc.id SKIP $offset LIMIT $limit",
            limit=limit,
            offset=offset,
        )
        return [_to_json_safe_node(dict(record["node"])) async for record in result]

    async def upsert_location(self, location: LocationNode) -> None:
        payload = location.model_dump(mode="json")
        await self._session.run(
            "MERGE (loc:Location {id: $id}) "
            "SET loc += $properties, loc.last_graph_updated_at = datetime()",
            id=location.id,
            properties=payload,
        )

    async def patch_world_state(self, body: WorldStatePatchBody) -> dict[str, Any]:
        set_payload = _serialize_world_state_patch(body)
        result = await self._session.run(
            "MERGE (w:WorldState {id: 'world'}) "
            "SET w += $set_fields, w.last_updated_at = datetime(), w.last_graph_updated_at = datetime() "
            "RETURN properties(w) AS node",
            set_fields=set_payload,
        )
        record = await result.single()
        return {} if record is None else _to_json_safe_node(dict(record["node"]))

    async def upsert_relates_to_edge(self, body: RelatesToEdgeBody) -> dict[str, Any]:
        """Create or update RELATES_TO while enforcing src/dst existence in one query."""

        result = await self._session.run(
            "MATCH (a:Character {id: $src_id}) "
            "MATCH (b:Character {id: $dst_id}) "
            "MERGE (a)-[r:RELATES_TO]->(b) "
            "SET r.trust = $trust, "
            "    r.fear = $fear, "
            "    r.affection = $affection, "
            "    r.last_updated_at = datetime() "
            "RETURN r.trust AS trust, r.fear AS fear, r.affection AS affection",
            src_id=body.src_id,
            dst_id=body.dst_id,
            trust=body.trust,
            fear=body.fear,
            affection=body.affection,
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type="character", node_id=f"{body.src_id}:{body.dst_id}")
        return {
            "edge_type": "RELATES_TO",
            "src_id": body.src_id,
            "dst_id": body.dst_id,
            "trust": int(record["trust"]),
            "fear": int(record["fear"]),
            "affection": int(record["affection"]),
        }

    async def upsert_knows_about_edge(self, body: KnowsAboutEdgeBody) -> dict[str, Any]:
        """Create or update KNOWS_ABOUT while enforcing node existence in one query."""

        result = await self._session.run(
            "MATCH (c:Character {id: $character_id}) "
            "MATCH (e:Event {id: $event_id}) "
            "MERGE (c)-[k:KNOWS_ABOUT]->(e) "
            "SET k.knowledge_state = $knowledge_state, "
            "    k.distortion_type = $distortion_type, "
            "    k.distortion_level = $distortion_level, "
            "    k.distorted_summary = $distorted_summary, "
            "    k.learned_at_tick = $learned_at_tick, "
            "    k.source_character_id = $source_character_id "
            "RETURN k.knowledge_state AS knowledge_state",
            character_id=body.character_id,
            event_id=body.event_id,
            knowledge_state=body.knowledge_state,
            distortion_type=body.distortion_type,
            distortion_level=body.distortion_level,
            distorted_summary=body.distorted_summary,
            learned_at_tick=body.learned_at_tick,
            source_character_id=body.source_character_id,
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type="character|event", node_id=f"{body.character_id}:{body.event_id}")
        return {
            "edge_type": "KNOWS_ABOUT",
            "character_id": body.character_id,
            "event_id": body.event_id,
            "knowledge_state": str(record["knowledge_state"]),
        }

    async def upsert_located_at_edge(self, body: LocatedAtEdgeBody) -> dict[str, Any]:
        """Create or update LOCATED_AT while enforcing node existence in one query."""

        result = await self._session.run(
            "MATCH (c:Character {id: $character_id}) "
            "MATCH (loc:Location {id: $location_id}) "
            "MERGE (c)-[l:LOCATED_AT]->(loc) "
            "SET l.arrived_at = datetime(), "
            "    l.is_permanent_resident = $is_permanent_resident "
            "RETURN l.is_permanent_resident AS is_permanent_resident",
            character_id=body.character_id,
            location_id=body.location_id,
            is_permanent_resident=body.is_permanent_resident,
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type="character|location", node_id=f"{body.character_id}:{body.location_id}")
        return {
            "edge_type": "LOCATED_AT",
            "character_id": body.character_id,
            "location_id": body.location_id,
            "is_permanent_resident": bool(record["is_permanent_resident"]),
        }

    async def upsert_participated_in_edge(self, body: ParticipatedInEdgeBody) -> dict[str, Any]:
        """Create or update PARTICIPATED_IN while enforcing node existence in one query."""

        result = await self._session.run(
            "MATCH (c:Character {id: $character_id}) "
            "MATCH (e:Event {id: $event_id}) "
            "MERGE (c)-[p:PARTICIPATED_IN]->(e) "
            "SET p.role = $role, "
            "    p.participated_at = datetime() "
            "RETURN p.role AS role",
            character_id=body.character_id,
            event_id=body.event_id,
            role=body.role,
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type="character|event", node_id=f"{body.character_id}:{body.event_id}")
        return {
            "edge_type": "PARTICIPATED_IN",
            "character_id": body.character_id,
            "event_id": body.event_id,
            "role": str(record["role"]),
        }

    async def delete_relates_to_edge(self, src_id: str, dst_id: str) -> bool:
        """Delete one RELATES_TO edge by path key."""

        result = await self._session.run(
            "MATCH (:Character {id: $src_id})-[r:RELATES_TO]->(:Character {id: $dst_id}) "
            "DELETE r "
            "RETURN 1 AS deleted",
            src_id=src_id,
            dst_id=dst_id,
        )
        return await result.single() is not None

    async def delete_knows_about_edge(self, character_id: str, event_id: str) -> bool:
        """Delete one KNOWS_ABOUT edge by path key."""

        result = await self._session.run(
            "MATCH (:Character {id: $character_id})-[k:KNOWS_ABOUT]->(:Event {id: $event_id}) "
            "DELETE k "
            "RETURN 1 AS deleted",
            character_id=character_id,
            event_id=event_id,
        )
        return await result.single() is not None

    async def delete_located_at_edge(self, character_id: str, location_id: str) -> bool:
        """Delete one LOCATED_AT edge by path key."""

        result = await self._session.run(
            "MATCH (:Character {id: $character_id})-[l:LOCATED_AT]->(:Location {id: $location_id}) "
            "DELETE l "
            "RETURN 1 AS deleted",
            character_id=character_id,
            location_id=location_id,
        )
        return await result.single() is not None

    async def delete_participated_in_edge(self, character_id: str, event_id: str) -> bool:
        """Delete one PARTICIPATED_IN edge by path key."""

        result = await self._session.run(
            "MATCH (:Character {id: $character_id})-[p:PARTICIPATED_IN]->(:Event {id: $event_id}) "
            "DELETE p "
            "RETURN 1 AS deleted",
            character_id=character_id,
            event_id=event_id,
        )
        return await result.single() is not None
