"""
serializer.py - Client-safe serialization helpers for registry introspection payloads.

Does NOT: load or merge registry contracts.

Dependencies injected: TypeRegistry.
"""

from typing import Any, Mapping

from npc_engine.type_registry.contracts import RuntimeEdgeTypeDefinition, RuntimeFieldDefinition, TypeRegistry


def serialize_registry_snapshot(*, registry: TypeRegistry) -> dict[str, Any]:
    """Serialize immutable registry state into a stable client-facing snapshot.

    Args:
        registry: Fully merged immutable type registry.

    Returns:
        Dictionary with schema_version, node_types, edge_types, and enum_extensions.
    """

    return {
        "schema_version": registry.schema_version,
        "node_types": _serialize_node_types(registry=registry),
        "edge_types": _serialize_edge_types(registry=registry),
        "enum_extensions": {name: list(values) for name, values in registry.enum_extensions.items()},
    }


def _serialize_node_types(*, registry: TypeRegistry) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    for node_name, base_fields in registry.base_node_types.items():
        core_fields = registry.core_types.get(node_name, {})
        custom_fields = registry.custom_node_types.get(node_name, {})
        fields: list[dict[str, Any]] = []
        fields.extend(_serialize_fields(base_fields=base_fields, origin="base"))
        fields.extend(_serialize_fields(base_fields=core_fields, origin="extension"))
        fields.extend(_serialize_fields(base_fields=custom_fields, origin="custom"))
        entries.append({"name": node_name, "fields": fields})

    for node_name, custom_fields in registry.custom_node_types.items():
        if node_name in registry.base_node_types:
            continue
        entries.append({"name": node_name, "fields": _serialize_fields(base_fields=custom_fields, origin="custom")})

    return sorted(entries, key=lambda item: str(item["name"]))


def _serialize_edge_types(*, registry: TypeRegistry) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    for edge_name, edge_definition in registry.base_edge_types.items():
        entries.append(_serialize_edge(name=edge_name, edge=edge_definition, origin="base"))
    for edge_name, edge_definition in registry.custom_edge_types.items():
        entries.append(_serialize_edge(name=edge_name, edge=edge_definition, origin="custom"))

    return sorted(entries, key=lambda item: str(item["name"]))


def _serialize_edge(*, name: str, edge: RuntimeEdgeTypeDefinition, origin: str) -> dict[str, Any]:
    return {
        "name": name,
        "field_origin": origin,
        "src_type": edge.src_type,
        "dst_type": edge.dst_type,
        "fields": _serialize_fields(base_fields=edge.fields, origin=origin),
    }


def _serialize_fields(*, base_fields: Mapping[str, RuntimeFieldDefinition], origin: str) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for field_name, definition in base_fields.items():
        fields.append(
            {
                "field_name": field_name,
                "field_type": definition.field_type,
                "field_origin": origin,
                "required": definition.required,
                "max_bytes": definition.max_bytes,
            }
        )
    return sorted(fields, key=lambda item: str(item["field_name"]))
