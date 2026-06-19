"""
merge_field_builders.py - Primitive field builders and merge enforcement helpers.
Layer: config
Purpose: Primitive field builders and merge enforcement helpers.

Does NOT: orchestrate registry merges or read files from disk.

Dependencies injected: validated schema field configs and runtime field contracts.
"""
from __future__ import annotations

from typing import Mapping, Protocol

from npc_engine.schema.schema_models import CustomEdgeTypeConfig, CustomFieldConfig, ExtensionField, FieldType
from npc_engine.type_registry.contracts import RuntimeEdgeTypeDefinition, RuntimeFieldDefinition
from npc_engine.utils.errors import RegistryValidationError


MAX_EXTENSION_FIELDS_PER_OBJECT = 16


class _FieldWithSharedProperties(Protocol):
    type: FieldType
    range: list[int | float] | None
    default: str | int | float | bool | None
    description: str
    indexed: bool


def runtime_edge(*, edge_config: CustomEdgeTypeConfig) -> RuntimeEdgeTypeDefinition:
    """Build an immutable RuntimeEdgeTypeDefinition from a custom edge schema config.

    Args:
        edge_config: Validated custom edge type configuration from the game schema.

    Returns:
        Immutable edge type definition with all fields resolved as RuntimeFieldDefinition.
    """
    from types import MappingProxyType

    fields = {
        field_name: runtime_field_from_custom(field=field_definition)
        for field_name, field_definition in edge_config.fields.items()
    }
    return RuntimeEdgeTypeDefinition(
        src_type=edge_config.src_type,
        dst_type=edge_config.dst_type,
        directional=edge_config.directional,
        cascade_on_delete=tuple(edge_config.cascade_on_delete),
        fields=MappingProxyType(fields),
    )


def runtime_field_from_extension(*, field: ExtensionField) -> RuntimeFieldDefinition:
    """Build a RuntimeFieldDefinition from a core-type extension field.

    Args:
        field: Validated extension field from a core type configuration.

    Returns:
        Immutable field definition with required=False and no collection item types.
    """
    return RuntimeFieldDefinition(
        field_type=field.type,
        required=False,
        range_limits=range_tuple(field=field),
        default=field.default,
        description=field.description,
        semantics=tuple(field.semantics),
        indexed=field.indexed,
        max_bytes=field.max_bytes,
        list_item_type=None,
        dict_value_type=None,
    )


def runtime_field_from_custom(*, field: CustomFieldConfig) -> RuntimeFieldDefinition:
    """Build a RuntimeFieldDefinition from a custom node/edge field config.

    Args:
        field: Validated custom field configuration from the game schema.

    Returns:
        Immutable field definition with required and indexed flags from the config.
    """
    return RuntimeFieldDefinition(
        field_type=field.type,
        required=field.required,
        range_limits=range_tuple(field=field),
        default=field.default,
        description=field.description,
        semantics=tuple(),
        indexed=field.indexed,
        max_bytes=field.max_bytes,
        list_item_type=None,
        dict_value_type=None,
    )


def validate_extension_field_count(
    *,
    owner_type: str,
    fields: Mapping[str, RuntimeFieldDefinition],
    source: str,
) -> None:
    """Raise RegistryValidationError if a type exceeds the extension field limit.

    Args:
        owner_type: Node or edge type name used in error messages.
        fields: Current field map after the latest merge step.
        source: Source path or label used in error messages.

    Raises:
        RegistryValidationError: If the field count exceeds MAX_EXTENSION_FIELDS_PER_OBJECT.
    """
    field_count = len(fields)
    if field_count <= MAX_EXTENSION_FIELDS_PER_OBJECT:
        return
    raise RegistryValidationError(
        source=source,
        detail=(
            f"extension field limit exceeded for {owner_type}: "
            f"{field_count} fields (max {MAX_EXTENSION_FIELDS_PER_OBJECT})"
        ),
    )


def merge_one_field(
    *,
    container: dict[str, RuntimeFieldDefinition],
    field_name: str,
    candidate: RuntimeFieldDefinition,
    owner_type: str,
    source: str,
) -> None:
    """Merge one extension field into an existing field map, enforcing no-mutation rules.

    Args:
        container: Mutable field dict being built for this merge step.
        field_name: Name of the field to add or verify.
        candidate: Proposed RuntimeFieldDefinition from the extension.
        owner_type: Parent type name, used in error messages.
        source: Extension source path, used in error messages.

    Raises:
        RegistryValidationError: If the field name collides with an existing declaration,
            or if the field definition differs from a previously declared one.
    """
    existing = container.get(field_name)
    if existing is None:
        container[field_name] = candidate
        return

    if existing != candidate:
        raise RegistryValidationError(
            source=source,
            detail=(
                f"constraint mutation for {owner_type}.{field_name} is not allowed "
                "after initial declaration"
            ),
        )

    raise RegistryValidationError(
        source=source,
        detail=f"field name {owner_type}.{field_name} collides with an existing declaration",
    )


def range_tuple(*, field: _FieldWithSharedProperties) -> tuple[int | float, int | float] | None:
    """Convert a field's range list into a two-element tuple or None.

    Args:
        field: Any field config that has a range attribute.

    Returns:
        Tuple of (lower, upper) bounds, or None if no range is defined.
    """
    if field.range is None:
        return None
    return (field.range[0], field.range[1])
