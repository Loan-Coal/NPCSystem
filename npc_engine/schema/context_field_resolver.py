"""
context_field_resolver.py - Resolves schema-tagged fields for context tiers.

Does NOT: query graph data.

Dependencies injected: SchemaConfig.
"""

from schema.schema_models import SchemaConfig
from schema.semantic_field_resolver import resolve_fields_with_semantic


def resolve_context_fields(schema: SchemaConfig) -> dict[str, list[str]]:
    """Return context tier mappings derived from schema semantics.

    Args:
        schema: SchemaConfig — the loaded and validated game schema.

    Returns:
        Dict mapping tier keys ("context_tier_0", "context_tier_a") to sorted field name lists.
    """

    return {
        "context_tier_0": resolve_fields_with_semantic(schema=schema, semantic="context_tier_0"),
        "context_tier_a": resolve_fields_with_semantic(schema=schema, semantic="context_tier_a"),
    }
