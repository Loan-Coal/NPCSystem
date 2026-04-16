"""
context_field_resolver.py - Resolves schema-tagged fields for context tiers.

Does NOT: query graph data.

Dependencies injected: SchemaConfig.
"""

from schema.schema_models import SchemaConfig


def resolve_context_fields(schema: SchemaConfig) -> dict[str, list[str]]:
    """Return context tier mappings derived from schema semantics."""

    tier0: list[str] = []
    tier_a: list[str] = []

    for type_config in schema.core_types.values():
        for field_name, field_config in type_config.extension_fields.items():
            if "context_tier_0" in field_config.semantics:
                tier0.append(field_name)
            if "context_tier_a" in field_config.semantics:
                tier_a.append(field_name)

    return {
        "context_tier_0": sorted(set(tier0)),
        "context_tier_a": sorted(set(tier_a)),
    }
