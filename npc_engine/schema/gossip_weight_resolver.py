"""
gossip_weight_resolver.py - Resolves schema-tagged gossip weight fields.

Does NOT: execute gossip selection logic.

Dependencies injected: SchemaConfig.
"""

from schema.schema_models import SchemaConfig


def resolve_gossip_weight_fields(schema: SchemaConfig) -> list[str]:
    """Return character extension fields tagged as gossip_weight."""

    character_config = schema.core_types.get("character")
    if character_config is None:
        return []

    fields = [
        field_name
        for field_name, field_config in character_config.extension_fields.items()
        if "gossip_weight" in field_config.semantics
    ]
    return sorted(set(fields))
