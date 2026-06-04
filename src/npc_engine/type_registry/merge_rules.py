"""
merge_rules.py - Applies additive-only merge rules for registry documents.
Layer: config
Purpose: (auto-detected — review)

Does NOT: read files from disk or build field definitions.

Dependencies injected: base schema model and validated extension documents.
"""

from types import MappingProxyType

from npc_engine.schema.schema_models import EnumExtensions, SchemaConfig
from npc_engine.type_registry.contracts import RuntimeEdgeTypeDefinition, RuntimeFieldDefinition, TypeRegistry
from npc_engine.type_registry.extension_loader import LoadedRegistryExtension
from npc_engine.type_registry.merge_field_builders import (
    merge_one_field,
    runtime_edge,
    runtime_field_from_custom,
    runtime_field_from_extension,
    validate_extension_field_count,
)
from npc_engine.utils.errors import RegistryValidationError


def merge_registry(
    *,
    base_schema: SchemaConfig,
    extensions: tuple[LoadedRegistryExtension, ...],
) -> TypeRegistry:
    """Build immutable registry state from base schema and validated extension docs.

    Args:
        base_schema: Validated game schema holding core and custom type declarations.
        extensions: Ordered tuple of validated extension documents to merge in.

    Returns:
        Partially built TypeRegistry with merged types and enum extensions.
        Base node/edge types and runtime models are NOT included; see registry.py.

    Raises:
        RegistryValidationError: If an extension introduces a collision or constraint mutation.
    """
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
            field_name: runtime_field_from_extension(field=field_definition)
            for field_name, field_definition in core_config.extension_fields.items()
        }
        validate_extension_field_count(
            owner_type=node_type,
            fields=merged[node_type],
            source="game_schema",
        )

    for extension in extensions:
        for node_type, core_config in extension.document.core_types.items():
            current_fields = merged.setdefault(node_type, {})
            for field_name, field_definition in core_config.extension_fields.items():
                candidate = runtime_field_from_extension(field=field_definition)
                merge_one_field(
                    container=current_fields,
                    field_name=field_name,
                    candidate=candidate,
                    owner_type=node_type,
                    source=extension.source_path,
                )
            validate_extension_field_count(
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
            field_name: runtime_field_from_custom(field=field_definition)
            for field_name, field_definition in node_config.fields.items()
        }
        validate_extension_field_count(
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
                field_name: runtime_field_from_custom(field=field_definition)
                for field_name, field_definition in node_config.fields.items()
            }
            validate_extension_field_count(
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
        merged[edge_type] = runtime_edge(edge_config=edge_config)
        validate_extension_field_count(
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
            merged[edge_type] = runtime_edge(edge_config=edge_config)
            validate_extension_field_count(
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
