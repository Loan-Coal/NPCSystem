"""
generic_graph_service.py - Registry-driven generic graph CRUD operations.

Does NOT: enforce auth scopes.

Dependencies injected: AsyncSession, TypeRegistry.
"""

from typing import Any, cast

from neo4j import AsyncSession

from type_registry.contracts import RuntimeEdgeTypeDefinition, RuntimeFieldDefinition, TypeRegistry
from type_registry.validation import RegistryOperation, validate_edge_payload, validate_node_payload
from graph.generic_graph_utils import (
    cypher_identifier,
    decode_properties,
    encode_properties,
    required_node_id,
    resolve_node_label,
)
from utils.errors import NodeNotFoundError, RegistryPayloadValidationError


class GenericGraphService:
    """Generic registry-backed graph node/edge read-write service."""

    def __init__(self, session: AsyncSession, registry: TypeRegistry):
        self._session = session
        self._registry = registry

    async def _run(self, query: str, **params: Any):
        return await self._session.run(cast(Any, query), **params)

    def missing_extension_warnings(self, *, node_type: str, node_payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Return structured warnings for missing extension values on one node payload."""

        node_key = node_type.strip().lower()
        extension_fields = self._registry.core_types.get(node_key, {})
        if len(extension_fields) == 0:
            return []

        warnings: list[dict[str, Any]] = []
        for field_name in sorted(extension_fields):
            if field_name in node_payload and node_payload[field_name] is not None:
                continue
            message = f"missing extension value for {node_key}.{field_name}"
            warning: dict[str, Any] = {
                "warning_code": "MISSING_EXTENSION_VALUE",
                "type": "extension_missing_value",
                "message": message,
                "node_type": node_key,
                "field_name": field_name,
            }
            node_id = node_payload.get("id")
            if isinstance(node_id, str) and node_id.strip() != "":
                warning["node_id"] = node_id
            warnings.append(warning)
        return warnings

    async def get_node(self, node_type: str, node_id: str) -> dict[str, Any] | None:
        node_key, node_label, field_defs = self._resolve_node_type(node_type=node_type)
        result = await self._run(
            f"MATCH (n:{cypher_identifier(node_label)} {{id: $id}}) RETURN properties(n) AS node",
            id=node_id,
        )
        record = await result.single()
        if record is None:
            return None
        return decode_properties(dict(record["node"]), field_defs)

    async def list_nodes(self, node_type: str, limit: int, offset: int) -> list[dict[str, Any]]:
        _, node_label, field_defs = self._resolve_node_type(node_type=node_type)
        result = await self._run(
            f"MATCH (n:{cypher_identifier(node_label)}) "
            "RETURN properties(n) AS node ORDER BY n.id SKIP $offset LIMIT $limit",
            limit=limit,
            offset=offset,
        )
        return [decode_properties(dict(record["node"]), field_defs) async for record in result]

    async def upsert_node(self, node_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        node_key, node_label, field_defs = self._resolve_node_type(node_type=node_type)
        validated = validate_node_payload(
            registry=self._registry,
            node_type=node_key,
            operation=RegistryOperation.CREATE,
            payload=payload,
        )
        node_id = required_node_id(validated)
        encoded = encode_properties(validated, field_defs)
        result = await self._run(
            f"MERGE (n:{cypher_identifier(node_label)} {{id: $id}}) "
            "SET n += $properties "
            "RETURN properties(n) AS node",
            id=node_id,
            properties=encoded,
        )
        record = await result.single()
        return decode_properties(dict(record["node"]), field_defs) if record is not None else validated

    async def patch_node(self, node_type: str, node_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        node_key, node_label, field_defs = self._resolve_node_type(node_type=node_type)
        existing = await self.get_node(node_type=node_key, node_id=node_id)
        if existing is None:
            raise NodeNotFoundError(node_type=node_key, node_id=node_id)
        merged = validate_node_payload(
            registry=self._registry,
            node_type=node_key,
            operation=RegistryOperation.PATCH,
            payload=payload,
            existing_payload=existing,
        )
        merged["id"] = node_id
        encoded = encode_properties(merged, field_defs)
        result = await self._run(
            f"MATCH (n:{cypher_identifier(node_label)} {{id: $id}}) "
            "SET n += $properties "
            "RETURN properties(n) AS node",
            id=node_id,
            properties=encoded,
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type=node_key, node_id=node_id)
        return decode_properties(dict(record["node"]), field_defs)

    async def get_edge(self, edge_type: str, src_id: str, dst_id: str) -> dict[str, Any] | None:
        edge_label, edge_def = self._resolve_edge_type(edge_type=edge_type)
        src_label = resolve_node_label(edge_def.src_type)
        dst_label = resolve_node_label(edge_def.dst_type)
        result = await self._run(
            f"MATCH (src:{cypher_identifier(src_label)} {{id: $src_id}})-"
            f"[e:{cypher_identifier(edge_label)}]->"
            f"(dst:{cypher_identifier(dst_label)} {{id: $dst_id}}) "
            "RETURN properties(e) AS edge, src.id AS src_id, dst.id AS dst_id",
            src_id=src_id,
            dst_id=dst_id,
        )
        record = await result.single()
        if record is None:
            return None
        return {
            "src_id": str(record["src_id"]),
            "dst_id": str(record["dst_id"]),
            **decode_properties(dict(record["edge"]), edge_def.fields),
        }

    async def list_edges(
        self,
        edge_type: str,
        limit: int,
        offset: int,
        src_id: str | None = None,
        dst_id: str | None = None,
    ) -> list[dict[str, Any]]:
        edge_label, edge_def = self._resolve_edge_type(edge_type=edge_type)
        src_label = resolve_node_label(edge_def.src_type)
        dst_label = resolve_node_label(edge_def.dst_type)
        where_parts: list[str] = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if src_id is not None:
            where_parts.append("src.id = $src_id")
            params["src_id"] = src_id
        if dst_id is not None:
            where_parts.append("dst.id = $dst_id")
            params["dst_id"] = dst_id
        where_clause = f"WHERE {' AND '.join(where_parts)} " if where_parts else ""
        result = await self._run(
            f"MATCH (src:{cypher_identifier(src_label)})-[e:{cypher_identifier(edge_label)}]->"
            f"(dst:{cypher_identifier(dst_label)}) "
            f"{where_clause}"
            "RETURN properties(e) AS edge, src.id AS src_id, dst.id AS dst_id "
            "ORDER BY src.id, dst.id SKIP $offset LIMIT $limit",
            **params,
        )
        return [
            {
                "src_id": str(record["src_id"]),
                "dst_id": str(record["dst_id"]),
                **decode_properties(dict(record["edge"]), edge_def.fields),
            }
            async for record in result
        ]

    async def upsert_edge(self, edge_type: str, src_id: str, dst_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        edge_label, edge_def = self._resolve_edge_type(edge_type=edge_type)
        validated = validate_edge_payload(
            registry=self._registry,
            edge_type=edge_label,
            operation=RegistryOperation.CREATE,
            payload=payload,
        )
        src_label = resolve_node_label(edge_def.src_type)
        dst_label = resolve_node_label(edge_def.dst_type)
        encoded = encode_properties(validated, edge_def.fields)
        result = await self._run(
            f"MATCH (src:{cypher_identifier(src_label)} {{id: $src_id}}) "
            f"MATCH (dst:{cypher_identifier(dst_label)} {{id: $dst_id}}) "
            f"MERGE (src)-[e:{cypher_identifier(edge_label)}]->(dst) "
            "SET e += $properties "
            "RETURN properties(e) AS edge, src.id AS src_id, dst.id AS dst_id",
            src_id=src_id,
            dst_id=dst_id,
            properties=encoded,
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type=f"{edge_def.src_type}|{edge_def.dst_type}", node_id=f"{src_id}:{dst_id}")
        return {
            "src_id": str(record["src_id"]),
            "dst_id": str(record["dst_id"]),
            **decode_properties(dict(record["edge"]), edge_def.fields),
        }

    async def delete_edge(self, edge_type: str, src_id: str, dst_id: str) -> bool:
        edge_label, edge_def = self._resolve_edge_type(edge_type=edge_type)
        src_label = resolve_node_label(edge_def.src_type)
        dst_label = resolve_node_label(edge_def.dst_type)
        result = await self._run(
            f"MATCH (src:{cypher_identifier(src_label)} {{id: $src_id}})-"
            f"[e:{cypher_identifier(edge_label)}]->"
            f"(dst:{cypher_identifier(dst_label)} {{id: $dst_id}}) "
            "DELETE e RETURN 1 AS deleted",
            src_id=src_id,
            dst_id=dst_id,
        )
        return await result.single() is not None

    def _resolve_node_type(self, node_type: str) -> tuple[str, str, dict[str, RuntimeFieldDefinition]]:
        node_key = node_type.strip().lower()
        base = self._registry.base_node_types.get(node_key)
        custom = self._registry.custom_node_types.get(node_type)
        if base is None and custom is None:
            raise RegistryPayloadValidationError(code="NODE_TYPE_UNKNOWN", detail=f"unknown node type: {node_type}")
        fields = dict(base or {})
        if custom is not None:
            fields.update(custom)
            return node_type, resolve_node_label(node_type), fields
        fields.update(self._registry.core_types.get(node_key, {}))
        return node_key, resolve_node_label(node_key), fields

    def _resolve_edge_type(self, edge_type: str) -> tuple[str, RuntimeEdgeTypeDefinition]:
        base_key = edge_type.strip().upper()
        base = self._registry.base_edge_types.get(base_key)
        if base is not None:
            return base_key, base
        custom = self._registry.custom_edge_types.get(edge_type)
        if custom is not None:
            return edge_type, custom
        raise RegistryPayloadValidationError(code="EDGE_TYPE_UNKNOWN", detail=f"unknown edge type: {edge_type}")
