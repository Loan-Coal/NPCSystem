"""
test_common_yaml_utils.py - Unit tests for shared YAML loading helpers.

Does NOT: validate domain-specific schema contracts.

Dependencies injected: None.
"""

from pathlib import Path

import pytest

from npc_engine.common.yaml_utils import load_yaml_mapping


def test_load_yaml_mapping_returns_dict_for_valid_mapping(tmp_path: Path) -> None:
    """A valid YAML mapping file should be parsed into a dict."""

    yaml_file = tmp_path / "npc_engine.config.yaml"
    yaml_file.write_text("key: value\nnested:\n  a: 1\n", encoding="utf-8")

    result = load_yaml_mapping(yaml_file, "Expected a mapping root")

    assert result == {"key": "value", "nested": {"a": 1}}


def test_load_yaml_mapping_raises_value_error_for_list_root(tmp_path: Path) -> None:
    """A YAML file whose root is a list should raise ValueError with the given message."""

    yaml_file = tmp_path / "list.yaml"
    yaml_file.write_text("- item1\n- item2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Expected a mapping root"):
        load_yaml_mapping(yaml_file, "Expected a mapping root")


def test_load_yaml_mapping_raises_value_error_for_scalar_root(tmp_path: Path) -> None:
    """A YAML file whose root is a scalar should raise ValueError."""

    yaml_file = tmp_path / "scalar.yaml"
    yaml_file.write_text("just a string\n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_yaml_mapping(yaml_file, "root must be a mapping")


def test_load_yaml_mapping_raises_file_not_found_for_missing_file(tmp_path: Path) -> None:
    """A missing file should propagate FileNotFoundError (not be swallowed)."""

    missing = tmp_path / "nonexistent.yaml"

    with pytest.raises(FileNotFoundError):
        load_yaml_mapping(missing, "root must be a mapping")


def test_load_yaml_mapping_preserves_custom_error_message(tmp_path: Path) -> None:
    """The caller-supplied error message must appear in the ValueError."""

    yaml_file = tmp_path / "bad.yaml"
    yaml_file.write_text("42\n", encoding="utf-8")

    custom_msg = "schema root must be a dict, got int"

    with pytest.raises(ValueError, match=custom_msg):
        load_yaml_mapping(yaml_file, custom_msg)
