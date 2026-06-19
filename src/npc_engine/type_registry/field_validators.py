"""
field_validators.py - Per-field type, range, and byte-limit validators for registry payloads.
Layer: config
Purpose: Per-field type, range, and byte-limit validators for registry payloads.

Does NOT: orchestrate payload-level validation or resolve edge/node definitions.

Dependencies injected: RuntimeFieldDefinition contracts.
"""
from __future__ import annotations

import json
from typing import Any

from npc_engine.type_registry.contracts import RuntimeFieldDefinition
from npc_engine.utils.errors import RegistryPayloadValidationError


def validate_field_type(*, field_name: str, value: Any, definition: RuntimeFieldDefinition) -> None:
    """Validate that a field value conforms to its declared field type.

    Args:
        field_name: Field name used in error messages.
        value: Non-null value to validate.
        definition: Runtime field contract specifying the expected type.

    Raises:
        RegistryPayloadValidationError: If the value does not match the declared type.
    """
    if definition.field_type == "list":
        _validate_list_shape(field_name=field_name, value=value, definition=definition)
        return

    if definition.field_type == "dict":
        _validate_dict_shape(field_name=field_name, value=value, definition=definition)
        return

    validators: dict[str, Any] = {
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


def validate_field_range(*, field_name: str, value: Any, definition: RuntimeFieldDefinition) -> None:
    """Validate that a numeric field value falls within its declared range.

    Args:
        field_name: Field name used in error messages.
        value: Non-null value to validate.
        definition: Runtime field contract specifying optional range_limits.

    Raises:
        RegistryPayloadValidationError: If the value is outside the declared range.
    """
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


def validate_field_byte_limit(*, field_name: str, value: Any, definition: RuntimeFieldDefinition) -> None:
    """Validate UTF-8 byte-size budget for one field value.

    Args:
        field_name: Field name used in error messages.
        value: Non-null value to validate.
        definition: Runtime field contract specifying max_bytes.

    Raises:
        RegistryPayloadValidationError: If the encoded size exceeds the declared byte limit.
    """
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


def _utf8_encoded_size(*, value: Any) -> int:
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    if isinstance(value, (int, float, bool)):
        return len(str(value).encode("utf-8"))
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return len(serialized.encode("utf-8"))
