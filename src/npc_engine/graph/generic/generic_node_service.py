"""
generic_node_service.py - Registry-driven generic node CRUD operations.
Layer: graph
Purpose: Registry-driven generic node CRUD operations.

Does NOT: enforce auth scopes or execute edge mutations.

Dependencies injected: AsyncSession, TypeRegistry (via _GenericGraphServiceBase).
"""
from __future__ import annotations

from typing import Any

from npc_engine.type_registry.contracts import RuntimeFieldDefinition
from npc_engine.type_registry.validation import RegistryOperation, validate_node_payload
from npc_engine.graph.generic.generic_graph_base import _GenericGraphServiceBase
from npc_engine.graph.generic.generic_graph_utils import (
    cypher_identifier,
    decode_properties,
    encode_properties,
    required_node_id,
    resolve_node_label,
)
from npc_engine.utils.errors import NodeNotFoundError, RegistryPayloadValidationError


class GenericNodeService(_GenericGraphServiceBase):
    """Registry-backed generic node read-write service."""

    def missing_extension_warnings(self, *, node_type: str, node_payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Return structured warnings for missing extension values on one node payload.

        Args:
            node_type: Registry node type key (e.g. "character").
            node_payload: Full node payload to scan for missing extension values.

        Returns:
            List of warning dicts, each with "warning_code", "type", "message", "node_type",
            "field_name", and optionally "node_id". Empty list when no fields are missing.
        """
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
        """Read one node by type and ID.

        Args:
            node_type: Registry node type key.
            node_id: Unique identifier of the node to read.

        Returns:
            Decoded property dict, or None if the node does not exist.
        """
        node_key, node_label, field_defs = self._resolve_node_type(node_type=node_type)
        result = await self._run(
            f"MATCH (n:{cypher_identifier(node_label)} {{id: $id}}) RETURN properties(n) AS node",
            id=node_id,
        )
        record = await result.single()
        await result.consume()
        if record is None:
            return None
        return decode_properties(dict(record["node"]), field_defs)

    async def list_nodes(self, node_type: str, limit: int, offset: int) -> list[dict[str, Any]]:
        """List all nodes of one type with pagination.

        Args:
            node_type: Registry node type key.
            limit: Maximum number of results to return.
            offset: Number of results to skip before returning.

        Returns:
            List of decoded property dicts ordered by node id.
        """
        _, node_label, field_defs = self._resolve_node_type(node_type=node_type)
        result = await self._run(
            f"MATCH (n:{cypher_identifier(node_label)}) "
            "RETURN properties(n) AS node ORDER BY n.id SKIP $offset LIMIT $limit",
            limit=limit,
            offset=offset,
        )
        try:
            return [decode_properties(dict(record["node"]), field_defs) async for record in result]
        finally:
            await result.consume()

    async def upsert_node(self, node_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Create or fully replace a node with the given payload.

        Args:
            node_type: Registry node type key.
            payload: Full property dict for the node, must include a non-empty "id" field.

        Returns:
            Decoded property dict reflecting the node's state after the write.

        Raises:
            RegistryPayloadValidationError: If payload fails schema or required-field validation.
        """
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
        await result.consume()
        return decode_properties(dict(record["node"]), field_defs) if record is not None else validated

    async def patch_node(self, node_type: str, node_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Apply a partial update to an existing node.

        Args:
            node_type: Registry node type key.
            node_id: Unique identifier of the node to patch.
            payload: Partial property dict; only supplied fields are updated.

        Returns:
            Decoded property dict reflecting the node's state after the patch.

        Raises:
            NodeNotFoundError: If no node with the given type and ID exists.
            RegistryPayloadValidationError: If the merged payload fails validation.
        """
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
        await result.consume()
        if record is None:
            raise NodeNotFoundError(node_type=node_key, node_id=node_id)
        return decode_properties(dict(record["node"]), field_defs)

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
