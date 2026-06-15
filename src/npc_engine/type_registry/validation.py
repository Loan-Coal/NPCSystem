"""
validation.py - Generic registry validation for node/edge payloads and topology.
Layer: config
Purpose: (auto-detected — review)

Does NOT: execute graph writes or perform field-level type coercion.

Dependencies injected: TypeRegistry.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

from npc_engine.type_registry.contracts import RuntimeEdgeTypeDefinition, RuntimeFieldDefinition, TypeRegistry
from npc_engine.type_registry.field_validators import validate_field_byte_limit, validate_field_range, validate_field_type
from npc_engine.utils.errors import RegistryPayloadValidationError


class RegistryOperation(str, Enum):
    """Supported operation modes for generic payload validation."""

    CREATE = "create"
    UPDATE = "update"
    PATCH = "patch"


def validate_edge_endpoint_types(*, registry: TypeRegistry, edge_type: str, src_type: str, dst_type: str) -> None:
    """Validate edge endpoint node types against registry topology declarations.

    Args:
        registry: Immutable type registry holding edge topology contracts.
        edge_type: Edge type name to look up (case-insensitive).
        src_type: Actual source node type to validate.
        dst_type: Actual destination node type to validate.

    Raises:
        RegistryPayloadValidationError: If the edge type is unknown or endpoints do not match.
    """
    edge_definition = _resolve_edge_definition(registry=registry, edge_type=edge_type)
    raw_src = edge_definition.src_type
    allowed_src = (
        {t.strip().lower() for t in raw_src}
        if isinstance(raw_src, tuple)
        else {raw_src.strip().lower()}
    )
    expected_dst = edge_definition.dst_type.strip().lower()
    actual_src = src_type.strip().lower()
    actual_dst = dst_type.strip().lower()
    if actual_src in allowed_src and expected_dst == actual_dst:
        return
    raise RegistryPayloadValidationError(
        code="EDGE_ENDPOINT_MISMATCH",
        detail=(
            f"edge endpoint mismatch for {edge_type}: expected src in ({','.join(sorted(allowed_src))}), "
            f"dst={expected_dst}, got ({actual_src},{actual_dst})"
        ),
    )


def validate_node_payload(
    *,
    registry: TypeRegistry,
    node_type: str,
    operation: RegistryOperation,
    payload: Mapping[str, Any],
    existing_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate generic node payload against base and extension field contracts.

    Args:
        registry: Immutable type registry holding node field contracts.
        node_type: Node type name to look up.
        operation: CREATE, UPDATE, or PATCH — controls required-field enforcement.
        payload: Incoming field values to validate.
        existing_payload: Current node state for PATCH merges (ignored otherwise).

    Returns:
        Validated payload dict; for PATCH, merged with existing_payload.

    Raises:
        RegistryPayloadValidationError: If the node type is unknown, fields are invalid,
            required fields are missing, or type/range/byte constraints are violated.
    """
    node_key = node_type.strip().lower()
    base_fields = registry.base_node_types.get(node_key)
    custom_fields = registry.custom_node_types.get(node_type)
    extension_fields = registry.core_types.get(node_key, {})

    if base_fields is None and custom_fields is None:
        raise RegistryPayloadValidationError(code="NODE_TYPE_UNKNOWN", detail=f"unknown node type: {node_type}")

    all_fields = dict(base_fields or {})
    if custom_fields is not None:
        all_fields.update(custom_fields)
    all_fields.update(extension_fields)

    _validate_unknown_fields(payload=payload, allowed_fields=all_fields, object_type=node_type)
    _validate_values(payload=payload, field_definitions=all_fields, base_fields=base_fields or {})
    _validate_required_fields(operation=operation, payload=payload, field_definitions=all_fields, object_type=node_type)

    if operation is RegistryOperation.PATCH:
        merged = dict(existing_payload or {})
        merged.update(dict(payload))
        return merged
    return dict(payload)


def validate_edge_payload(
    *,
    registry: TypeRegistry,
    edge_type: str,
    operation: RegistryOperation,
    payload: Mapping[str, Any],
    existing_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate generic edge payload against edge field contracts.

    Args:
        registry: Immutable type registry holding edge field contracts.
        edge_type: Edge type name to look up (case-insensitive for base edges).
        operation: CREATE, UPDATE, or PATCH — controls required-field enforcement.
        payload: Incoming field values to validate.
        existing_payload: Current edge state for PATCH merges (ignored otherwise).

    Returns:
        Validated payload dict; for PATCH, merged with existing_payload.

    Raises:
        RegistryPayloadValidationError: If the edge type is unknown, fields are invalid,
            required fields are missing, or type/range/byte constraints are violated.
    """
    edge_definition = _resolve_edge_definition(registry=registry, edge_type=edge_type)
    field_definitions = dict(edge_definition.fields)
    required_fields = {k: v for k, v in field_definitions.items() if v.required}
    _validate_unknown_fields(payload=payload, allowed_fields=field_definitions, object_type=edge_type)
    _validate_values(payload=payload, field_definitions=field_definitions, base_fields=required_fields)
    _validate_required_fields(operation=operation, payload=payload, field_definitions=field_definitions, object_type=edge_type)

    if operation is RegistryOperation.PATCH:
        merged = dict(existing_payload or {})
        merged.update(dict(payload))
        return merged
    return dict(payload)


def _resolve_edge_definition(*, registry: TypeRegistry, edge_type: str) -> RuntimeEdgeTypeDefinition:
    edge_key = edge_type.strip().upper()
    edge_definition = registry.base_edge_types.get(edge_key)
    if edge_definition is not None:
        return edge_definition

    custom_definition = registry.custom_edge_types.get(edge_type)
    if custom_definition is not None:
        return custom_definition

    raise RegistryPayloadValidationError(code="EDGE_TYPE_UNKNOWN", detail=f"unknown edge type: {edge_type}")


def _validate_unknown_fields(
    *,
    payload: Mapping[str, Any],
    allowed_fields: Mapping[str, RuntimeFieldDefinition],
    object_type: str,
) -> None:
    unknown = sorted(name for name in payload if name not in allowed_fields)
    if not unknown:
        return
    unknown_names = ", ".join(unknown)
    raise RegistryPayloadValidationError(
        code="UNKNOWN_FIELD",
        detail=f"unknown fields for {object_type}: {unknown_names}",
    )


def _validate_values(
    *,
    payload: Mapping[str, Any],
    field_definitions: Mapping[str, RuntimeFieldDefinition],
    base_fields: Mapping[str, RuntimeFieldDefinition],
) -> None:
    for field_name, value in payload.items():
        definition = field_definitions[field_name]
        if value is None:
            if field_name in base_fields and base_fields[field_name].required:
                raise RegistryPayloadValidationError(
                    code="BASE_FIELD_NULL_FORBIDDEN",
                    detail=f"null is not allowed for base field: {field_name}",
                )
            continue

        validate_field_type(field_name=field_name, value=value, definition=definition)
        validate_field_range(field_name=field_name, value=value, definition=definition)
        validate_field_byte_limit(field_name=field_name, value=value, definition=definition)


def _validate_required_fields(
    *,
    operation: RegistryOperation,
    payload: Mapping[str, Any],
    field_definitions: Mapping[str, RuntimeFieldDefinition],
    object_type: str,
) -> None:
    if operation is RegistryOperation.PATCH:
        return

    missing_required = [
        field_name
        for field_name, definition in field_definitions.items()
        if definition.required and (field_name not in payload or payload[field_name] is None)
    ]
    if not missing_required:
        return

    joined = ", ".join(sorted(missing_required))
    raise RegistryPayloadValidationError(
        code="REQUIRED_FIELD_MISSING",
        detail=f"required fields missing for {object_type}: {joined}",
    )
