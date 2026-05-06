"""
test_type_registry_validator.py - Unit tests for R2 registry topology and payload validators.

Does NOT: execute API routes or graph writes.

Dependencies injected: none.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from npc_engine.type_registry.registry import build_type_registry
from npc_engine.schema.schema_loader import load_game_schema
from npc_engine.type_registry.validation import (
    RegistryOperation,
    validate_edge_endpoint_types,
    validate_edge_payload,
    validate_node_payload,
)
from npc_engine.utils.errors import RegistryPayloadValidationError


@pytest.fixture()
def registry_fixture(tmp_path: Path):
    schema_path = tmp_path / "game_schema.yaml"
    schema_path.write_text(
        """
schema_version: "1.0"
core_types:
  character:
    extension_fields:
      legacy_title:
        type: str
      influence:
        type: int
        range: [0, 100]
enum_extensions:
  event_type: []
  participation_role: []
""".strip(),
        encoding="utf-8",
    )
    base_schema = load_game_schema(schema_path=str(schema_path))
    return build_type_registry(base_schema=base_schema, extension_sources=())


def test_validate_edge_endpoint_types_rejects_invalid_pair(registry_fixture) -> None:
    """Edge endpoint validation should fail when src/dst types do not match registry definition."""

    with pytest.raises(RegistryPayloadValidationError, match="endpoint"):
        validate_edge_endpoint_types(
            registry=registry_fixture,
            edge_type="KNOWS_ABOUT",
            src_type="character",
            dst_type="location",
        )


def test_validate_node_payload_requires_base_fields_on_create(registry_fixture) -> None:
    """Create validation should reject missing required base fields."""

    with pytest.raises(RegistryPayloadValidationError, match="required"):
        validate_node_payload(
            registry=registry_fixture,
            node_type="character",
            operation=RegistryOperation.CREATE,
            payload={"name": "Aria"},
        )


def test_validate_node_payload_rejects_null_base_field_on_patch(registry_fixture) -> None:
    """PATCH should reject explicit null on base fields."""

    with pytest.raises(RegistryPayloadValidationError, match="null"):
        validate_node_payload(
            registry=registry_fixture,
            node_type="character",
            operation=RegistryOperation.PATCH,
            payload={"name": None},
            existing_payload={"name": "Aria"},
        )


def test_validate_node_payload_allows_null_extension_field_on_patch(registry_fixture) -> None:
    """PATCH should allow explicit null for extension fields and keep omitted values."""

    merged = validate_node_payload(
        registry=registry_fixture,
        node_type="character",
        operation=RegistryOperation.PATCH,
        payload={"legacy_title": None},
        existing_payload={"name": "Aria", "legacy_title": "Captain"},
    )

    assert merged["name"] == "Aria"
    assert merged["legacy_title"] is None


def test_validate_node_payload_rejects_extension_range_violation(registry_fixture) -> None:
    """Validation should enforce extension field range constraints."""

    with pytest.raises(RegistryPayloadValidationError, match="range"):
        validate_node_payload(
            registry=registry_fixture,
            node_type="character",
            operation=RegistryOperation.CREATE,
            payload={
                "id": "c1",
                "name": "Aria",
                "archetype": "guard",
                "biography": "A city guard",
                "legacy_title": "Captain",
                "influence": 500,
            },
        )


def test_validate_edge_payload_checks_field_shape(registry_fixture) -> None:
    """Edge payload validation should enforce type/range constraints for edge properties."""

    with pytest.raises(RegistryPayloadValidationError, match="type"):
        validate_edge_payload(
            registry=registry_fixture,
            edge_type="RELATES_TO",
            operation=RegistryOperation.CREATE,
            payload={
                "trust": "high",
                "fear": 10,
                "affection": 20,
            },
        )


def test_validate_node_payload_accepts_list_dict_base_shapes(registry_fixture) -> None:
    """Base contract list/dict fields should accept correctly typed collection payloads."""

    validated = validate_node_payload(
        registry=registry_fixture,
        node_type="world_state",
        operation=RegistryOperation.CREATE,
        payload={
            "id": "world",
            "epoch": "age_of_peace",
            "faction_standings": {"guild": 10},
            "active_conditions": ["rain"],
            "weather": "storm",
            "last_updated_at": "2026-05-01T00:00:00Z",
            "last_graph_updated_at": "2026-05-01T00:00:00Z",
        },
    )

    assert validated["faction_standings"] == {"guild": 10}
    assert validated["active_conditions"] == ["rain"]


def test_validate_node_payload_rejects_invalid_list_item_shape(registry_fixture) -> None:
    """Base contract typed list fields should reject mixed non-conforming item values."""

    with pytest.raises(RegistryPayloadValidationError, match="list\\[str\\]"):
        validate_node_payload(
            registry=registry_fixture,
            node_type="world_state",
            operation=RegistryOperation.CREATE,
            payload={
                "id": "world",
                "epoch": "age_of_peace",
                "faction_standings": {},
                "active_conditions": ["rain", 42],
                "weather": "clear",
                "last_updated_at": "2026-04-19T00:00:00Z",
                "last_graph_updated_at": "2026-04-19T00:00:00Z",
            },
        )
