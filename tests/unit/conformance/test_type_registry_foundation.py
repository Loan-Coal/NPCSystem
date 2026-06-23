"""
test_type_registry_foundation.py - Unit tests for type-registry R1 foundation behavior.

Does NOT: exercise graph endpoint routing or database writes.

Dependencies injected: tmp_path and monkeypatch fixtures.
"""

from pathlib import Path

import pytest
pytest.importorskip("neo4j")

from npc_engine.api.dependencies import get_game_schema, get_type_registry
from npc_engine.config import get_settings
from npc_engine.schema.schema_loader import load_game_schema
from npc_engine.type_registry.registry import build_type_registry
from npc_engine.utils.errors import RegistryValidationError


def _write_base_schema(path: Path) -> None:
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
        semantics: [gossip_weight]
enum_extensions:
  event_type: [ritual]
  participation_role: [mediator]
""".strip(),
        encoding="utf-8",
    )


def _write_extension(path: Path, content: str) -> None:
    path.write_text(content.strip(), encoding="utf-8")


def test_build_type_registry_merges_additive_extension_fields(tmp_path: Path) -> None:
    """Registry builder should merge additive extension fields from extension YAML files."""

    schema_path = tmp_path / "game_schema.yaml"
    extension_path = tmp_path / "character_extension.yaml"
    _write_base_schema(path=schema_path)
    _write_extension(
        path=extension_path,
        content="""
core_types:
  character:
    extension_fields:
      reputation:
        type: int
        range: [0, 100]
        default: 10
        semantics: [context_tier_a]
""",
    )

    base_schema = load_game_schema(schema_path=str(schema_path))
    registry = build_type_registry(
        base_schema=base_schema,
        extension_sources=(str(extension_path),),
    )

    assert "character" in registry.core_types
    assert "bravery" in registry.core_types["character"]
    assert "reputation" in registry.core_types["character"]


def test_build_type_registry_rejects_base_field_name_collision(tmp_path: Path) -> None:
    """Registry merge should fail when extension field collides with an existing base/extension field name."""

    schema_path = tmp_path / "game_schema.yaml"
    extension_path = tmp_path / "duplicate_extension.yaml"
    _write_base_schema(path=schema_path)
    _write_extension(
        path=extension_path,
        content="""
core_types:
  character:
    extension_fields:
      bravery:
        type: int
        range: [0, 100]
        default: 50
        semantics: [gossip_weight]
""",
    )

    base_schema = load_game_schema(schema_path=str(schema_path))

    with pytest.raises(RegistryValidationError, match="collides"):
        build_type_registry(
            base_schema=base_schema,
            extension_sources=(str(extension_path),),
        )


def test_build_type_registry_rejects_constraint_mutation(tmp_path: Path) -> None:
    """Registry merge should reject post-declaration constraint mutation for the same field."""

    schema_path = tmp_path / "game_schema.yaml"
    first_extension = tmp_path / "first_extension.yaml"
    second_extension = tmp_path / "second_extension.yaml"
    _write_base_schema(path=schema_path)

    _write_extension(
        path=first_extension,
        content="""
core_types:
  character:
    extension_fields:
      social_rank:
        type: int
        range: [0, 10]
        default: 1
""",
    )
    _write_extension(
        path=second_extension,
        content="""
core_types:
  character:
    extension_fields:
      social_rank:
        type: int
        range: [0, 20]
        default: 1
""",
    )

    base_schema = load_game_schema(schema_path=str(schema_path))

    with pytest.raises(RegistryValidationError, match="constraint"):
        build_type_registry(
            base_schema=base_schema,
            extension_sources=(str(first_extension), str(second_extension)),
        )


def test_build_type_registry_rejects_invalid_extension_document(tmp_path: Path) -> None:
    """Registry build should fail fast when an extension file root is not a YAML object."""

    schema_path = tmp_path / "game_schema.yaml"
    extension_path = tmp_path / "invalid_extension.yaml"
    _write_base_schema(path=schema_path)
    _write_extension(
        path=extension_path,
        content="""
- invalid
- extension
""",
    )

    base_schema = load_game_schema(schema_path=str(schema_path))

    with pytest.raises(RegistryValidationError, match="YAML object"):
        build_type_registry(
            base_schema=base_schema,
            extension_sources=(str(extension_path),),
        )


def test_get_type_registry_returns_immutable_singleton(monkeypatch, tmp_path: Path) -> None:
    """Dependency provider should return one immutable singleton for process runtime."""

    schema_path = tmp_path / "game_schema.yaml"
    extension_path = tmp_path / "extension.yaml"
    _write_base_schema(path=schema_path)
    _write_extension(
        path=extension_path,
        content="""
core_types:
  character:
    extension_fields:
      rumor_resistance:
        type: int
        range: [0, 100]
        default: 30
""",
    )

    monkeypatch.setenv("API_KEY_SECRET", "local_dev_secret_change_this_2026")
    monkeypatch.setenv("GAME_SCHEMA_PATH", str(schema_path))
    monkeypatch.setenv("TYPE_REGISTRY_EXTENSION_SOURCES", str(extension_path))

    get_settings.cache_clear()
    get_game_schema.cache_clear()
    get_type_registry.cache_clear()

    first_registry = get_type_registry()
    second_registry = get_type_registry()

    assert first_registry is second_registry

    with pytest.raises(TypeError):
        first_registry.core_types["character"]["new_field"] = object()
