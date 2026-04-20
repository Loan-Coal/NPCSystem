"""
test_registry_serializer.py - Unit tests for registry introspection serialization.

Does NOT: exercise HTTP routing or graph I/O.

Dependencies injected: tmp_path fixture.
"""

from pathlib import Path

from schema.schema_loader import load_game_schema
from type_registry.registry import build_type_registry
from type_registry.serializer import serialize_registry_snapshot


def test_serialize_registry_snapshot_exposes_field_origins(tmp_path: Path) -> None:
    """Introspection serializer should expose stable field origin metadata for clients."""

    schema_path = tmp_path / "game_schema.yaml"
    schema_path.write_text(
        """
schema_version: "1.0"
core_types:
  character:
    extension_fields:
      reputation:
        type: int
enum_extensions:
  event_type: []
  participation_role: []
""".strip(),
        encoding="utf-8",
    )

    registry = build_type_registry(base_schema=load_game_schema(schema_path=str(schema_path)), extension_sources=())
    snapshot = serialize_registry_snapshot(registry=registry)

    character = next(item for item in snapshot["node_types"] if item["name"] == "character")
    origins = {field["field_name"]: field["field_origin"] for field in character["fields"]}

    assert snapshot["schema_version"] == "1.0"
    assert origins["id"] == "base"
    assert origins["reputation"] == "extension"
