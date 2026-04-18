"""
test_semantic_field_resolver.py - Unit tests for semantic-tag field selection helper.

Does NOT: read schema files from disk.

Dependencies injected: None.
"""

from schema.schema_models import SchemaConfig
from schema.semantic_field_resolver import resolve_fields_with_semantic


def _build_schema() -> SchemaConfig:
    return SchemaConfig.model_validate(
        {
            "schema_version": "1.0",
            "core_types": {
                "character": {
                    "extension_fields": {
                        "bravery": {"type": "int", "semantics": ["gossip_weight"]},
                        "trust_notes": {"type": "str", "semantics": ["context_tier_a"]},
                    }
                },
                "event": {
                    "extension_fields": {
                        "impact": {"type": "int", "semantics": ["context_tier_0", "context_tier_a"]}
                    }
                },
            },
        }
    )


def test_resolve_fields_with_semantic_across_all_types() -> None:
    """Helper should return deduplicated sorted field names across core types."""

    schema = _build_schema()

    assert resolve_fields_with_semantic(schema=schema, semantic="context_tier_a") == ["impact", "trust_notes"]


def test_resolve_fields_with_semantic_for_one_core_type() -> None:
    """Helper should scope semantic selection to one core type when requested."""

    schema = _build_schema()

    assert resolve_fields_with_semantic(schema=schema, semantic="gossip_weight", core_type="character") == ["bravery"]
    assert resolve_fields_with_semantic(schema=schema, semantic="gossip_weight", core_type="location") == []
