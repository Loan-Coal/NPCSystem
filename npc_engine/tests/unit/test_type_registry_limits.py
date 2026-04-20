"""
test_type_registry_limits.py - Unit tests for registry payload and extension-count limits.

Does NOT: run API route handlers.

Dependencies injected: tmp_path fixture.
"""

from pathlib import Path

import pytest

from schema.schema_loader import load_game_schema
from type_registry.registry import build_type_registry
from type_registry.validation import RegistryOperation, validate_node_payload
from utils.errors import RegistryPayloadValidationError, RegistryValidationError


def test_validate_node_payload_rejects_field_value_over_byte_limit(tmp_path: Path) -> None:
    """Payload validation should reject values whose UTF-8 byte size exceeds field max."""

    schema_path = tmp_path / "game_schema.yaml"
    schema_path.write_text(
        """
schema_version: "1.0"
core_types: {}
enum_extensions:
  event_type: []
  participation_role: []
""".strip(),
        encoding="utf-8",
    )

    registry = build_type_registry(base_schema=load_game_schema(schema_path=str(schema_path)), extension_sources=())

    with pytest.raises(RegistryPayloadValidationError, match="byte"):
        validate_node_payload(
            registry=registry,
            node_type="character",
            operation=RegistryOperation.CREATE,
            payload={
                "id": "c1",
                "name": "a" * 513,
                "archetype": "guard",
                "biography": "bio",
                "current_location_id": "loc-1",
                "is_player": False,
                "is_active": True,
                "gossipy": 10,
                "credulity": 10,
                "honesty": 10,
            },
        )


def test_build_registry_rejects_more_than_sixteen_extension_fields(tmp_path: Path) -> None:
    """Registry build should reject object types that declare too many extension fields."""

    schema_path = tmp_path / "game_schema.yaml"
    many_fields = "\n".join(f"      extra_{index}: {{ type: int }}" for index in range(17))
    schema_path.write_text(
        (
            "schema_version: \"1.0\"\n"
            "core_types:\n"
            "  character:\n"
            "    extension_fields:\n"
            f"{many_fields}\n"
            "enum_extensions:\n"
            "  event_type: []\n"
            "  participation_role: []\n"
        ),
        encoding="utf-8",
    )

    with pytest.raises(RegistryValidationError, match="16"):
        build_type_registry(base_schema=load_game_schema(schema_path=str(schema_path)), extension_sources=())
