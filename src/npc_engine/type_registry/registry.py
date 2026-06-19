"""
registry.py - Facade for building immutable type registry state.
Layer: config
Purpose: Facade for building immutable type registry state.

Does NOT: perform request-time graph validation.

Dependencies injected: base schema + configured extension paths.
"""
from __future__ import annotations

import dataclasses

from npc_engine.schema.schema_models import SchemaConfig
from npc_engine.type_registry.base_contract_loader import load_base_edge_types, load_base_node_types
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.type_registry.extension_loader import load_registry_extensions
from npc_engine.type_registry.merge_rules import merge_registry
from npc_engine.type_registry.runtime_models import build_runtime_models


def build_type_registry(*, base_schema: SchemaConfig, extension_sources: tuple[str, ...]) -> TypeRegistry:
    """Build immutable registry from base schema plus optional extension documents.

    Two-phase construction is intentional: runtime_models require the node/edge type
    definitions to be present before they can generate Pydantic models, so a structural
    registry is built first, then the model maps are merged in via dataclasses.replace.

    Args:
        base_schema: Validated game schema loaded from the primary YAML.
        extension_sources: Tuple of file paths or glob patterns for extension YAMLs.

    Returns:
        Fully merged, immutable TypeRegistry with base types, extensions, and runtime models.

    Raises:
        RegistryValidationError: If any extension source path is invalid or contains conflicts.
    """

    loaded_extensions = load_registry_extensions(extension_sources=extension_sources)
    extension_registry = merge_registry(base_schema=base_schema, extensions=loaded_extensions)
    structural = TypeRegistry(
        schema_version=extension_registry.schema_version,
        base_node_types=load_base_node_types(),
        base_edge_types=load_base_edge_types(),
        core_types=extension_registry.core_types,
        custom_node_types=extension_registry.custom_node_types,
        custom_edge_types=extension_registry.custom_edge_types,
        enum_extensions=extension_registry.enum_extensions,
    )
    runtime_models = build_runtime_models(registry=structural)
    return dataclasses.replace(
        structural,
        node_models=runtime_models.node_models,
        edge_models=runtime_models.edge_models,
    )
