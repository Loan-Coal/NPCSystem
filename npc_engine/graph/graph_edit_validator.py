"""
graph_edit_validator.py - Validation helpers for typed graph edit payloads.

Does NOT: execute graph writes.

Dependencies injected: SchemaConfig.
"""

from typing import Any

from schema.schema_models import SchemaConfig
from utils.errors import ImmutableFieldError, SchemaValidationError


IMMUTABLE_FIELDS_BY_TYPE = {
    "character": {"id", "is_player", "created_at"},
    "event": {"id", "location_id", "occurred_at", "tick_id", "event_type", "participants"},
    "location": {"id"},
}


def ensure_no_immutable_fields(node_type: str, set_fields: dict[str, Any]) -> None:
    """Reject patch operations that attempt to modify immutable fields."""

    for field_name in set_fields:
        if field_name in IMMUTABLE_FIELDS_BY_TYPE.get(node_type, set()):
            raise ImmutableFieldError(field_name=field_name, node_type=node_type)


def validate_extension_fields(
    schema: SchemaConfig,
    node_type: str,
    extension_fields: dict[str, Any] | None,
) -> None:
    """Validate extension fields against loaded schema declarations."""

    if not extension_fields:
        return

    type_config = schema.core_types.get(node_type)
    declared = type_config.extension_fields if type_config else {}

    unknown = [name for name in extension_fields if name not in declared]
    if unknown:
        names = ", ".join(sorted(unknown))
        raise SchemaValidationError(
            schema_path="runtime",
            detail=f"unknown extension fields for {node_type}: {names}",
        )
