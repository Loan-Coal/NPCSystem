"""
semantic_field_resolver.py - Shared field selection by semantic tags.
Layer: config
Purpose: Shared field selection by semantic tags.

Does NOT: load schema files or resolve graph data.

Dependencies injected: SchemaConfig.
"""
from __future__ import annotations

from npc_engine.schema.schema_models import SchemaConfig, SemanticTag


def resolve_fields_with_semantic(
    schema: SchemaConfig,
    semantic: SemanticTag,
    core_type: str | None = None,
) -> list[str]:
    """Return unique sorted extension fields tagged with one semantic.

    Args:
        schema: SchemaConfig — the loaded and validated game schema.
        semantic: SemanticTag — the tag to filter on (e.g. "context_tier_0").
        core_type: str | None — if given, restrict search to that core type only;
            if None, search across all core types.

    Returns:
        Sorted list of unique field names that carry the requested semantic tag.
        Returns [] if core_type is specified but not found in the schema.
    """

    if core_type is None:
        type_configs = list(schema.core_types.values())
    else:
        selected_type = schema.core_types.get(core_type)
        if selected_type is None:
            return []
        type_configs = [selected_type]

    fields = {
        field_name
        for type_config in type_configs
        for field_name, field_config in type_config.extension_fields.items()
        if semantic in field_config.semantics
    }
    return sorted(fields)
