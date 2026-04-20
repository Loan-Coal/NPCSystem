"""
merge_rules.py - Applies additive-only merge rules for registry documents.

Does NOT: read files from disk.

Dependencies injected: base schema model and validated extension documents.
"""

from types import MappingProxyType
from typing import Mapping, Protocol

from schema.schema_models import CustomEdgeTypeConfig, CustomFieldConfig, EnumExtensions, ExtensionField, SchemaConfig
from type_registry.contracts import RuntimeEdgeTypeDefinition, RuntimeFieldDefinition, TypeRegistry
from type_registry.extension_loader import LoadedRegistryExtension
from utils.errors import RegistryValidationError


MAX_EXTENSION_FIELDS_PER_OBJECT = 16


class _FieldWithSharedProperties(Protocol):
    type: str
    range: list[int | float] | None
    default: str | int | float | bool | None
    description: str
    indexed: bool


def merge_registry(
    *,
    base_schema: SchemaConfig,
    extensions: tuple[LoadedRegistryExtension, ...],
) -> TypeRegistry:
    """Build immutable registry state from base schema and validated extension docs."""

    core_types = _merge_core_types(base_schema=base_schema, extensions=extensions)
    custom_node_types = _merge_custom_node_types(base_schema=base_schema, extensions=extensions)
    custom_edge_types = _merge_custom_edge_types(base_schema=base_schema, extensions=extensions)
    enum_extensions = _merge_enum_extensions(base_enum=base_schema.enum_extensions, extensions=extensions)

    return TypeRegistry(
        schema_version=base_schema.schema_version,
        core_types=core_types,
        custom_node_types=custom_node_types,
        custom_edge_types=custom_edge_types,
        enum_extensions=enum_extensions,
    )


def _merge_core_types(
    *,
    base_schema: SchemaConfig,
    extensions: tuple[LoadedRegistryExtension, ...],
) -> MappingProxyType[str, MappingProxyType[str, RuntimeFieldDefinition]]:
    merged: dict[str, dict[str, RuntimeFieldDefinition]] = {}
    for node_type, core_config in base_schema.core_types.items():
        merged[node_type] = {
            field_name: _runtime_field_from_extension(field=field_definition)
            for field_name, field_definition in core_config.extension_fields.items()
        }
        _validate_extension_field_count(
            owner_type=node_type,
            fields=merged[node_type],
            source="game_schema",
        )

    for extension in extensions:
        for node_type, core_config in extension.document.core_types.items():
            current_fields = merged.setdefault(node_type, {})
            for field_name, field_definition in core_config.extension_fields.items():
                candidate = _runtime_field_from_extension(field=field_definition)
                _merge_one_field(
                    container=current_fields,
                    field_name=field_name,
                    candidate=candidate,
                    owner_type=node_type,
                    source=extension.source_path,
                )
            _validate_extension_field_count(
                owner_type=node_type,
                fields=current_fields,
                source=extension.source_path,
            )

    frozen = {node_type: MappingProxyType(fields.copy()) for node_type, fields in merged.items()}
    return MappingProxyType(frozen)


def _merge_custom_node_types(
    *,
    base_schema: SchemaConfig,
    extensions: tuple[LoadedRegistryExtension, ...],
) -> MappingProxyType[str, MappingProxyType[str, RuntimeFieldDefinition]]:
    merged: dict[str, dict[str, RuntimeFieldDefinition]] = {}
    for node_type, node_config in base_schema.custom_node_types.items():
        merged[node_type] = {
            field_name: _runtime_field_from_custom(field=field_definition)
            for field_name, field_definition in node_config.fields.items()
        }
        _validate_extension_field_count(
            owner_type=node_type,
            fields=merged[node_type],
            source="game_schema",
        )

    for extension in extensions:
        for node_type, node_config in extension.document.custom_node_types.items():
            if node_type in merged:
                raise RegistryValidationError(
                    source=extension.source_path,
                    detail=f"custom node type {node_type} collides with an existing declaration",
                )
            merged[node_type] = {
                field_name: _runtime_field_from_custom(field=field_definition)
                for field_name, field_definition in node_config.fields.items()
            }
            _validate_extension_field_count(
                owner_type=node_type,
                fields=merged[node_type],
                source=extension.source_path,
            )

    frozen = {node_type: MappingProxyType(fields.copy()) for node_type, fields in merged.items()}
    return MappingProxyType(frozen)


def _merge_custom_edge_types(
    *,
    base_schema: SchemaConfig,
    extensions: tuple[LoadedRegistryExtension, ...],
) -> MappingProxyType[str, RuntimeEdgeTypeDefinition]:
    merged: dict[str, RuntimeEdgeTypeDefinition] = {}
    for edge_type, edge_config in base_schema.custom_edge_types.items():
        merged[edge_type] = _runtime_edge(edge_config=edge_config)
        _validate_extension_field_count(
            owner_type=edge_type,
            fields=merged[edge_type].fields,
            source="game_schema",
        )

    for extension in extensions:
        for edge_type, edge_config in extension.document.custom_edge_types.items():
            if edge_type in merged:
                raise RegistryValidationError(
                    source=extension.source_path,
                    detail=f"custom edge type {edge_type} collides with an existing declaration",
                )
            merged[edge_type] = _runtime_edge(edge_config=edge_config)
            _validate_extension_field_count(
                owner_type=edge_type,
                fields=merged[edge_type].fields,
                source=extension.source_path,
            )

    return MappingProxyType(merged)


def _merge_enum_extensions(
    *,
    base_enum: EnumExtensions,
    extensions: tuple[LoadedRegistryExtension, ...],
) -> MappingProxyType[str, tuple[str, ...]]:
    event_types = list(base_enum.event_type)
    participation_roles = list(base_enum.participation_role)

    for extension in extensions:
        event_types.extend(extension.document.enum_extensions.event_type)
        participation_roles.extend(extension.document.enum_extensions.participation_role)

    return MappingProxyType(
        {
            "event_type": tuple(dict.fromkeys(event_types)),
            "participation_role": tuple(dict.fromkeys(participation_roles)),
        }
    )


def _runtime_edge(*, edge_config: CustomEdgeTypeConfig) -> RuntimeEdgeTypeDefinition:
    fields = {
        field_name: _runtime_field_from_custom(field=field_definition)
        for field_name, field_definition in edge_config.fields.items()
    }
    return RuntimeEdgeTypeDefinition(
        src_type=edge_config.src_type,
        dst_type=edge_config.dst_type,
        directional=edge_config.directional,
        cascade_on_delete=tuple(edge_config.cascade_on_delete),
        fields=MappingProxyType(fields),
    )


def _runtime_field_from_extension(*, field: ExtensionField) -> RuntimeFieldDefinition:
    return RuntimeFieldDefinition(
        field_type=field.type,
        required=False,
        range_limits=_range_tuple(field=field),
        default=field.default,
        description=field.description,
        semantics=tuple(field.semantics),
        indexed=field.indexed,
        max_bytes=field.max_bytes,
        list_item_type=None,
        dict_value_type=None,
    )


def _runtime_field_from_custom(*, field: CustomFieldConfig) -> RuntimeFieldDefinition:
    return RuntimeFieldDefinition(
        field_type=field.type,
        required=field.required,
        range_limits=_range_tuple(field=field),
        default=field.default,
        description=field.description,
        semantics=tuple(),
        indexed=field.indexed,
        max_bytes=field.max_bytes,
        list_item_type=None,
        dict_value_type=None,
    )


def _validate_extension_field_count(
    *,
    owner_type: str,
    fields: Mapping[str, RuntimeFieldDefinition],
    source: str,
) -> None:
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


def _range_tuple(*, field: _FieldWithSharedProperties) -> tuple[int | float, int | float] | None:
    if field.range is None:
        return None
    return (field.range[0], field.range[1])


def _merge_one_field(
    *,
    container: dict[str, RuntimeFieldDefinition],
    field_name: str,
    candidate: RuntimeFieldDefinition,
    owner_type: str,
    source: str,
) -> None:
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
