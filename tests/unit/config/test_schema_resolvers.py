"""
test_schema_resolvers.py - Unit tests for schema field resolvers, enum validator, and model factory.

Does NOT: load YAML files or touch graph state.

Dependencies injected: None.
"""

import pytest

from npc_engine.schema.context_field_resolver import resolve_context_fields
from npc_engine.schema.enum_validator import build_enum_values
from npc_engine.schema.gossip_weight_resolver import resolve_gossip_weight_fields
from npc_engine.schema.model_factory import generate_runtime_models
from npc_engine.schema.schema_models import (
    CoreTypeConfig,
    EnumExtensions,
    ExtensionField,
    SchemaConfig,
)
from npc_engine.schema.semantic_field_resolver import resolve_fields_with_semantic


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_schema(
    character_fields: dict[str, ExtensionField] | None = None,
    npc_fields: dict[str, ExtensionField] | None = None,
    enum_extensions: EnumExtensions | None = None,
) -> SchemaConfig:
    core_types: dict[str, CoreTypeConfig] = {}
    if character_fields is not None:
        core_types["character"] = CoreTypeConfig(extension_fields=character_fields)
    if npc_fields is not None:
        core_types["npc"] = CoreTypeConfig(extension_fields=npc_fields)

    return SchemaConfig(
        schema_version="1.0",
        core_types=core_types,
        enum_extensions=enum_extensions or EnumExtensions(),
    )


def _int_field(semantics: list[str]) -> ExtensionField:
    return ExtensionField(type="int", semantics=semantics)  # type: ignore[arg-type]


# ── semantic_field_resolver ───────────────────────────────────────────────────


def test_resolve_fields_with_semantic_returns_sorted_unique_across_all_types() -> None:
    """When core_type is None, fields from all types with the semantic are returned sorted."""

    schema = _make_schema(
        character_fields={"bravery": _int_field(["gossip_weight"]), "trust": _int_field(["gossip_weight"])},
        npc_fields={"aggression": _int_field(["gossip_weight"])},
    )

    result = resolve_fields_with_semantic(schema=schema, semantic="gossip_weight")

    assert result == ["aggression", "bravery", "trust"]


def test_resolve_fields_with_semantic_filters_by_core_type() -> None:
    """When core_type is given, only that type's fields are searched."""

    schema = _make_schema(
        character_fields={"bravery": _int_field(["gossip_weight"])},
        npc_fields={"aggression": _int_field(["gossip_weight"])},
    )

    result = resolve_fields_with_semantic(schema=schema, semantic="gossip_weight", core_type="npc")

    assert result == ["aggression"]


def test_resolve_fields_with_semantic_returns_empty_for_unknown_type() -> None:
    """An unknown core_type should return an empty list, not raise."""

    schema = _make_schema(character_fields={"bravery": _int_field(["gossip_weight"])})

    result = resolve_fields_with_semantic(schema=schema, semantic="gossip_weight", core_type="ghost")

    assert result == []


def test_resolve_fields_with_semantic_returns_only_matching_semantics() -> None:
    """Fields tagged with a different semantic should not appear in results."""

    schema = _make_schema(
        character_fields={
            "bravery": _int_field(["gossip_weight"]),
            "mood": _int_field(["context_tier_0"]),
        }
    )

    result = resolve_fields_with_semantic(schema=schema, semantic="gossip_weight")

    assert result == ["bravery"]
    assert "mood" not in result


# ── context_field_resolver ────────────────────────────────────────────────────


def test_resolve_context_fields_returns_correct_tier_keys() -> None:
    """Result dict must contain exactly the tier_0 and tier_a keys."""

    schema = _make_schema()
    result = resolve_context_fields(schema=schema)

    assert set(result.keys()) == {"context_tier_0", "context_tier_a"}


def test_resolve_context_fields_maps_semantics_to_correct_tiers() -> None:
    """Fields tagged tier_0 and tier_a should appear in the right bucket."""

    schema = _make_schema(
        character_fields={
            "name": _int_field(["context_tier_0"]),
            "reputation": _int_field(["context_tier_a"]),
        }
    )

    result = resolve_context_fields(schema=schema)

    assert "name" in result["context_tier_0"]
    assert "reputation" in result["context_tier_a"]
    assert "name" not in result["context_tier_a"]


# ── gossip_weight_resolver ────────────────────────────────────────────────────


def test_resolve_gossip_weight_fields_returns_character_fields() -> None:
    """Only character-type fields tagged gossip_weight should be returned."""

    schema = _make_schema(
        character_fields={
            "bravery": _int_field(["gossip_weight"]),
            "trust": _int_field(["context_tier_0"]),
        },
        npc_fields={"aggression": _int_field(["gossip_weight"])},
    )

    result = resolve_gossip_weight_fields(schema=schema)

    assert result == ["bravery"]


def test_resolve_gossip_weight_fields_returns_empty_when_no_character_type() -> None:
    """A schema without a 'character' core type should return an empty list."""

    schema = _make_schema(npc_fields={"aggression": _int_field(["gossip_weight"])})

    result = resolve_gossip_weight_fields(schema=schema)

    assert result == []


# ── enum_validator ────────────────────────────────────────────────────────────


def test_build_enum_values_includes_base_event_types() -> None:
    """Base event types must always be present in the result."""

    schema = _make_schema()
    result = build_enum_values(schema=schema)

    assert "crime" in result.event_type
    assert "battle" in result.event_type


def test_build_enum_values_merges_schema_extensions() -> None:
    """Schema-defined extension values must be merged with the base set."""

    extensions = EnumExtensions(event_type=["ritual"], participation_role=["spy"])
    schema = _make_schema(enum_extensions=extensions)

    result = build_enum_values(schema=schema)

    assert "ritual" in result.event_type
    assert "spy" in result.participation_role
    assert "crime" in result.event_type


def test_build_enum_values_returns_frozensets() -> None:
    """EnumValueSet fields must be frozensets (immutable)."""

    schema = _make_schema()
    result = build_enum_values(schema=schema)

    assert isinstance(result.event_type, frozenset)
    assert isinstance(result.participation_role, frozenset)


def test_build_enum_values_result_is_frozen_dataclass() -> None:
    """EnumValueSet is a frozen dataclass — mutation must raise."""

    schema = _make_schema()
    result = build_enum_values(schema=schema)

    with pytest.raises(Exception):
        result.event_type = frozenset()  # type: ignore[misc]


# ── model_factory ─────────────────────────────────────────────────────────────


def test_generate_runtime_models_creates_one_model_per_core_type() -> None:
    """One model should be generated for each core type in the schema."""

    schema = _make_schema(
        character_fields={"bravery": _int_field([])},
        npc_fields={"aggression": _int_field([])},
    )

    models = generate_runtime_models(schema=schema)

    assert set(models.keys()) == {"character", "npc"}


def test_generate_runtime_models_model_accepts_valid_field_values() -> None:
    """Generated model should accept a value within the declared range."""

    schema = _make_schema(
        character_fields={
            "bravery": ExtensionField(type="int", range=[0, 100], default=50)
        }
    )

    models = generate_runtime_models(schema=schema)
    instance = models["character"](bravery=75)

    assert instance.bravery == 75  # type: ignore[attr-defined]


def test_generate_runtime_models_model_rejects_value_outside_range() -> None:
    """Generated model should reject a field value outside the declared range."""

    from pydantic import ValidationError

    schema = _make_schema(
        character_fields={
            "bravery": ExtensionField(type="int", range=[0, 100], default=50)
        }
    )

    models = generate_runtime_models(schema=schema)

    with pytest.raises(ValidationError):
        models["character"](bravery=200)


def test_generate_runtime_models_model_name_follows_convention() -> None:
    """Generated model class name should follow '<TypeName>ExtensionModel' pattern."""

    schema = _make_schema(character_fields={"bravery": _int_field([])})

    models = generate_runtime_models(schema=schema)

    assert models["character"].__name__ == "CharacterExtensionModel"


def test_generate_runtime_models_returns_empty_for_schema_with_no_core_types() -> None:
    """A schema with no core types should return an empty dict."""

    schema = _make_schema()

    models = generate_runtime_models(schema=schema)

    assert models == {}
