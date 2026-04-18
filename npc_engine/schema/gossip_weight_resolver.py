"""
gossip_weight_resolver.py - Resolves schema-tagged gossip weight fields.

Does NOT: execute gossip selection logic.

Dependencies injected: SchemaConfig.
"""

from schema.schema_models import SchemaConfig
from schema.semantic_field_resolver import resolve_fields_with_semantic


def resolve_gossip_weight_fields(schema: SchemaConfig) -> list[str]:
    """Return character extension fields tagged as gossip_weight."""

    return resolve_fields_with_semantic(schema=schema, semantic="gossip_weight", core_type="character")
