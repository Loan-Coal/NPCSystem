"""
generic_edge_service.py - Registry-driven generic edge CRUD operations.
Layer: graph
Purpose: Registry-driven generic edge CRUD operations.

Does NOT: enforce auth scopes or execute node mutations.

Dependencies injected: AsyncSession, TypeRegistry (via _GenericGraphServiceBase).
"""
from __future__ import annotations

from typing import Any

from npc_engine.type_registry.contracts import RuntimeEdgeTypeDefinition
from npc_engine.type_registry.validation import RegistryOperation, validate_edge_payload
from npc_engine.graph.generic_graph_base import _GenericGraphServiceBase
from npc_engine.graph.generic_graph_utils import cypher_identifier, decode_properties, encode_properties, resolve_node_label, resolve_src_label_expr
from npc_engine.utils.errors import NodeNotFoundError, RegistryPayloadValidationError


class GenericEdgeService(_GenericGraphServiceBase):
    """Registry-backed generic edge read-write service."""

    async def get_edge(self, edge_type: str, src_id: str, dst_id: str) -> dict[str, Any] | None:
        """Read one directed edge by type and endpoint IDs.

        Args:
            edge_type: Registry edge type label (e.g. "RELATES_TO").
            src_id: ID of the source node.
            dst_id: ID of the destination node.

        Returns:
            Dict with "src_id", "dst_id", and decoded edge properties, or None if not found.
        """
        edge_label, edge_def = self._resolve_edge_type(edge_type=edge_type)
        src_expr = resolve_src_label_expr(edge_def.src_type)
        dst_label = resolve_node_label(edge_def.dst_type)
        result = await self._run(
            f"MATCH (src:{src_expr} {{id: $src_id}})-"
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
        """List directed edges of one type with optional endpoint filtering and pagination.

        Args:
            edge_type: Registry edge type label.
            limit: Maximum number of results to return.
            offset: Number of results to skip before returning.
            src_id: If provided, filter to edges originating from this node.
            dst_id: If provided, filter to edges terminating at this node.

        Returns:
            List of dicts each containing "src_id", "dst_id", and decoded edge properties.
        """
        edge_label, edge_def = self._resolve_edge_type(edge_type=edge_type)
        src_expr = resolve_src_label_expr(edge_def.src_type)
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
            f"MATCH (src:{src_expr})-[e:{cypher_identifier(edge_label)}]->"
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
        """Create or update a directed edge between two existing nodes.

        Args:
            edge_type: Registry edge type label.
            src_id: ID of the source node; must exist in the graph.
            dst_id: ID of the destination node; must exist in the graph.
            payload: Full property dict for the edge, validated against the type contract.

        Returns:
            Dict with "src_id", "dst_id", and decoded edge properties after the write.

        Raises:
            NodeNotFoundError: If either endpoint node is missing from the graph.
            RegistryPayloadValidationError: If payload fails schema or required-field validation.
        """
        edge_label, edge_def = self._resolve_edge_type(edge_type=edge_type)
        validated = validate_edge_payload(
            registry=self._registry,
            edge_type=edge_label,
            operation=RegistryOperation.CREATE,
            payload=payload,
        )
        src_expr = resolve_src_label_expr(edge_def.src_type)
        dst_label = resolve_node_label(edge_def.dst_type)
        encoded = encode_properties(validated, edge_def.fields)
        result = await self._run(
            f"MATCH (src:{src_expr} {{id: $src_id}}) "
            f"MATCH (dst:{cypher_identifier(dst_label)} {{id: $dst_id}}) "
            f"MERGE (src)-[e:{cypher_identifier(edge_label)}]->(dst) "
            "SET e += $properties "
            "RETURN properties(e) AS edge, src.id AS src_id, dst.id AS dst_id",
            src_id=src_id,
            dst_id=dst_id,
            properties=encoded,
        )
        record = await result.single()
        src_type_str = "|".join(edge_def.src_type) if isinstance(edge_def.src_type, tuple) else edge_def.src_type
        if record is None:
            raise NodeNotFoundError(node_type=f"{src_type_str}|{edge_def.dst_type}", node_id=f"{src_id}:{dst_id}")
        return {
            "src_id": str(record["src_id"]),
            "dst_id": str(record["dst_id"]),
            **decode_properties(dict(record["edge"]), edge_def.fields),
        }

    async def delete_edge(self, edge_type: str, src_id: str, dst_id: str) -> bool:
        """Delete a directed edge between two nodes.

        Args:
            edge_type: Registry edge type label.
            src_id: ID of the source node.
            dst_id: ID of the destination node.

        Returns:
            True if the edge was found and deleted; False if it did not exist.
        """
        edge_label, edge_def = self._resolve_edge_type(edge_type=edge_type)
        src_expr = resolve_src_label_expr(edge_def.src_type)
        dst_label = resolve_node_label(edge_def.dst_type)
        result = await self._run(
            f"MATCH (src:{src_expr} {{id: $src_id}})-"
            f"[e:{cypher_identifier(edge_label)}]->"
            f"(dst:{cypher_identifier(dst_label)} {{id: $dst_id}}) "
            "DELETE e RETURN 1 AS deleted",
            src_id=src_id,
            dst_id=dst_id,
        )
        return await result.single() is not None

    def _resolve_edge_type(self, edge_type: str) -> tuple[str, RuntimeEdgeTypeDefinition]:
        base_key = edge_type.strip().upper()
        base = self._registry.base_edge_types.get(base_key)
        if base is not None:
            return base_key, base
        custom = self._registry.custom_edge_types.get(edge_type)
        if custom is not None:
            return edge_type, custom
        raise RegistryPayloadValidationError(code="EDGE_TYPE_UNKNOWN", detail=f"unknown edge type: {edge_type}")
