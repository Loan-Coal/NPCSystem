"""
validation.py - Generic registry validation for node/edge payloads and topology.

Does NOT: execute graph writes.

Dependencies injected: TypeRegistry.
"""

from enum import Enum
import json
from typing import Any, Mapping

from type_registry.contracts import RuntimeEdgeTypeDefinition, RuntimeFieldDefinition, TypeRegistry
from utils.errors import RegistryPayloadValidationError


class RegistryOperation(str, Enum):
    """Supported operation modes for generic payload validation."""

    CREATE = "create"
    UPDATE = "update"
    PATCH = "patch"


def validate_edge_endpoint_types(*, registry: TypeRegistry, edge_type: str, src_type: str, dst_type: str) -> None:
    """Validate edge endpoint node types against registry topology declarations."""

    edge_definition = _resolve_edge_definition(registry=registry, edge_type=edge_type)
    expected_src = edge_definition.src_type.strip().lower()
    expected_dst = edge_definition.dst_type.strip().lower()
    actual_src = src_type.strip().lower()
    actual_dst = dst_type.strip().lower()
    if expected_src == actual_src and expected_dst == actual_dst:
        return
    raise RegistryPayloadValidationError(
        code="EDGE_ENDPOINT_MISMATCH",
        detail=(
            f"edge endpoint mismatch for {edge_type}: expected ({expected_src},{expected_dst}), "
            f"got ({actual_src},{actual_dst})"
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
    """Validate generic node payload against base and extension field contracts."""

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
    """Validate generic edge payload against edge field contracts."""

    edge_definition = _resolve_edge_definition(registry=registry, edge_type=edge_type)
    field_definitions = dict(edge_definition.fields)
    _validate_unknown_fields(payload=payload, allowed_fields=field_definitions, object_type=edge_type)
    _validate_values(payload=payload, field_definitions=field_definitions, base_fields=field_definitions)
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
            if field_name in base_fields:
                raise RegistryPayloadValidationError(
                    code="BASE_FIELD_NULL_FORBIDDEN",
                    detail=f"null is not allowed for base field: {field_name}",
                )
            continue

        _validate_field_type(field_name=field_name, value=value, definition=definition)
        _validate_field_range(field_name=field_name, value=value, definition=definition)
        _validate_field_byte_limit(field_name=field_name, value=value, definition=definition)


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


def _validate_field_type(*, field_name: str, value: Any, definition: RuntimeFieldDefinition) -> None:
    if definition.field_type == "list":
        _validate_list_shape(field_name=field_name, value=value, definition=definition)
        return

    if definition.field_type == "dict":
        _validate_dict_shape(field_name=field_name, value=value, definition=definition)
        return

    validators = {
        "str": lambda item: isinstance(item, str),
        "int": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "float": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "bool": lambda item: isinstance(item, bool),
    }
    validator = validators[definition.field_type]
    if validator(value):
        return

    raise RegistryPayloadValidationError(
        code="FIELD_TYPE_INVALID",
        detail=f"field type invalid for {field_name}: expected {definition.field_type}",
    )


def _validate_list_shape(*, field_name: str, value: Any, definition: RuntimeFieldDefinition) -> None:
    if not isinstance(value, list):
        raise RegistryPayloadValidationError(
            code="FIELD_TYPE_INVALID",
            detail=f"field type invalid for {field_name}: expected list",
        )

    if definition.list_item_type is None:
        return

    for item in value:
        if _is_expected_primitive(value=item, expected_type=definition.list_item_type):
            continue
        raise RegistryPayloadValidationError(
            code="FIELD_TYPE_INVALID",
            detail=f"field type invalid for {field_name}: expected list[{definition.list_item_type}]",
        )


def _validate_dict_shape(*, field_name: str, value: Any, definition: RuntimeFieldDefinition) -> None:
    if not isinstance(value, dict):
        raise RegistryPayloadValidationError(
            code="FIELD_TYPE_INVALID",
            detail=f"field type invalid for {field_name}: expected dict",
        )

    if any(not isinstance(key, str) for key in value):
        raise RegistryPayloadValidationError(
            code="FIELD_TYPE_INVALID",
            detail=f"field type invalid for {field_name}: expected dict[str, ...]",
        )

    if definition.dict_value_type is None:
        return

    for item in value.values():
        if _is_expected_primitive(value=item, expected_type=definition.dict_value_type):
            continue
        raise RegistryPayloadValidationError(
            code="FIELD_TYPE_INVALID",
            detail=(
                f"field type invalid for {field_name}: "
                f"expected dict[str, {definition.dict_value_type}]"
            ),
        )


def _is_expected_primitive(*, value: Any, expected_type: str) -> bool:
    validators = {
        "str": lambda item: isinstance(item, str),
        "int": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "float": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
        "bool": lambda item: isinstance(item, bool),
    }
    return validators[expected_type](value)


def _validate_field_range(*, field_name: str, value: Any, definition: RuntimeFieldDefinition) -> None:
    if definition.range_limits is None:
        return

    lower, upper = definition.range_limits
    numeric_value = float(value)
    if lower <= numeric_value <= upper:
        return

    raise RegistryPayloadValidationError(
        code="FIELD_RANGE_INVALID",
        detail=f"field range invalid for {field_name}: expected {lower}..{upper}",
    )


def _validate_field_byte_limit(*, field_name: str, value: Any, definition: RuntimeFieldDefinition) -> None:
    """Validate UTF-8 byte-size budget for one field value."""

    encoded_size = _utf8_encoded_size(value=value)
    if encoded_size <= definition.max_bytes:
        return
    raise RegistryPayloadValidationError(
        code="FIELD_BYTE_LIMIT_EXCEEDED",
        detail=(
            f"field byte limit exceeded for {field_name}: "
            f"{encoded_size} bytes (max {definition.max_bytes})"
        ),
    )


def _utf8_encoded_size(*, value: Any) -> int:
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    if isinstance(value, (int, float, bool)):
        return len(str(value).encode("utf-8"))
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return len(serialized.encode("utf-8"))
