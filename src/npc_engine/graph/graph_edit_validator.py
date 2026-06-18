"""
graph_edit_validator.py - Validation helpers for typed graph edit payloads.
Layer: graph
Purpose: (auto-detected — review)

Does NOT: execute graph writes.

Dependencies injected: SchemaConfig.
"""
from __future__ import annotations

from typing import Any

from npc_engine.schema.schema_models import SchemaConfig
from npc_engine.utils.errors import ImmutableFieldError, SchemaValidationError


IMMUTABLE_FIELDS_BY_TYPE = {
    "character": {"id", "is_player", "created_at"},
    "event": {"id", "location_id", "occurred_at", "tick_id", "event_type", "participants"},
    "location": {"id"},
}


def ensure_no_immutable_fields(node_type: str, set_fields: dict[str, Any]) -> None:
    """Reject patch operations that attempt to modify immutable fields.

    Args:
        node_type: Registry node type key (e.g. "character").
        set_fields: Dict of fields included in the patch request.

    Raises:
        ImmutableFieldError: If any field in set_fields is declared immutable for node_type.
    """

    for field_name in set_fields:
        if field_name in IMMUTABLE_FIELDS_BY_TYPE.get(node_type, set()):
            raise ImmutableFieldError(field_name=field_name, node_type=node_type)


def validate_extension_fields(
    schema: SchemaConfig,
    node_type: str,
    extension_fields: dict[str, Any] | None,
) -> None:
    """Validate extension fields against loaded schema declarations.

    Args:
        schema: Loaded game schema configuration providing declared extension fields per type.
        node_type: Registry node type key to look up declared extension fields for.
        extension_fields: Extension field dict from the request payload; no-op if None or empty.

    Raises:
        SchemaValidationError: If any extension field name is not declared in the schema.
    """

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
