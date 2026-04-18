"""
semantic_field_resolver.py - Shared field selection by semantic tags.

Does NOT: load schema files or resolve graph data.

Dependencies injected: SchemaConfig.
"""

from schema.schema_models import SchemaConfig, SemanticTag


def resolve_fields_with_semantic(
    schema: SchemaConfig,
    semantic: SemanticTag,
    core_type: str | None = None,
) -> list[str]:
    """Return unique sorted extension fields tagged with one semantic."""

    if core_type is None:
        type_configs = schema.core_types.values()
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
