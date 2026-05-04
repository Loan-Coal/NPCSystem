"""
test_schema_loader.py - Unit tests for schema file loading and validation.

Does NOT: test API route behavior.

Dependencies injected: tmp_path fixture.
"""

from pathlib import Path

import pytest

from schema.schema_loader import load_game_schema
from utils.errors import SchemaMisconfiguredError


def _write_schema(path: Path) -> None:
    path.write_text(
        """
schema_version: "1.0"
core_types:
  character:
    extension_fields:
      bravery:
        type: int
        range: [0, 100]
        default: 50
        description: "Bravery score"
        semantics: [gossip_weight]
        indexed: false
enum_extensions:
  event_type: [ritual]
""".strip(),
        encoding="utf-8",
    )


def test_load_game_schema_valid_file(tmp_path: Path) -> None:
    """Schema loader should parse a valid schema file."""

    schema_path = tmp_path / "game_schema.yaml"
    _write_schema(path=schema_path)

    schema = load_game_schema(schema_path=str(schema_path))

    assert schema.schema_version == "1.0"
    assert "character" in schema.core_types
    assert schema.enum_extensions.event_type == ["ritual"]


def test_load_game_schema_raises_when_missing(tmp_path: Path) -> None:
    """Schema loader should fail fast if the schema file is missing."""

    missing_path = tmp_path / "missing_schema.yaml"

    with pytest.raises(SchemaMisconfiguredError):
        load_game_schema(schema_path=str(missing_path))


def test_load_game_schema_raises_typed_error_on_read_failure(monkeypatch, tmp_path: Path) -> None:
    """Schema loader should wrap file read failures as misconfiguration errors."""

    schema_path = tmp_path / "game_schema.yaml"
    _write_schema(path=schema_path)

    def _raise_os_error(*args, **kwargs):
        raise OSError("read failed")

    monkeypatch.setattr(Path, "read_text", _raise_os_error)

    with pytest.raises(SchemaMisconfiguredError):
        load_game_schema(schema_path=str(schema_path))


def test_load_game_schema_raises_validation_error_for_list_root(tmp_path: Path) -> None:
    """A schema YAML whose root is a list should raise SchemaValidationError."""

    from utils.errors import SchemaValidationError

    schema_path = tmp_path / "bad.yaml"
    schema_path.write_text("- item1\n- item2\n", encoding="utf-8")

    with pytest.raises(SchemaValidationError):
        load_game_schema(schema_path=str(schema_path))


def test_load_game_schema_raises_validation_error_for_wrong_version(tmp_path: Path) -> None:
    """A schema with an unsupported schema_version should raise SchemaValidationError."""

    from utils.errors import SchemaValidationError

    schema_path = tmp_path / "bad_version.yaml"
    schema_path.write_text('schema_version: "99.0"\n', encoding="utf-8")

    with pytest.raises(SchemaValidationError):
        load_game_schema(schema_path=str(schema_path))


def test_load_game_schema_raises_validation_error_for_invalid_field_type(tmp_path: Path) -> None:
    """A schema with an unrecognised extension field type should raise SchemaValidationError."""

    from utils.errors import SchemaValidationError

    schema_path = tmp_path / "bad_field.yaml"
    schema_path.write_text(
        """
schema_version: "1.0"
core_types:
  character:
    extension_fields:
      bad_field:
        type: uuid
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(SchemaValidationError):
        load_game_schema(schema_path=str(schema_path))
