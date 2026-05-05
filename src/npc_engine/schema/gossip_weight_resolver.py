"""
gossip_weight_resolver.py - Resolves schema-tagged gossip weight fields.

Does NOT: execute gossip selection logic.

Dependencies injected: SchemaConfig.
"""

from npc_engine.schema.schema_models import SchemaConfig
from npc_engine.schema.semantic_field_resolver import resolve_fields_with_semantic


def resolve_gossip_weight_fields(schema: SchemaConfig) -> list[str]:
    """Return character extension fields tagged as gossip_weight.

    Args:
        schema: SchemaConfig — the loaded and validated game schema.

    Returns:
        Sorted list of field names on the "character" core type tagged as gossip_weight.
        Returns [] if no such fields exist or "character" is not a core type.
    """

    return resolve_fields_with_semantic(schema=schema, semantic="gossip_weight", core_type="character")
