"""
test_llm_config_loader_v14.py - Unit tests for v1.4 llm_config YAML loading.

Does NOT: run dialogue orchestration.

Dependencies injected: tmp_path fixture.
"""

from pathlib import Path

import pytest

from npc_engine.schema.llm_config_loader import load_llm_config
from npc_engine.utils.errors import LLMConfigMisconfiguredError, LLMConfigValidationError


def _write_valid_llm_config(path: Path) -> None:
    path.write_text(
        """
prompt_schema_version: "v1.4"
compression_prompt_version: "v1.4"
tier_budget_tokens:
  tier_a: 4000
  tier_b: 3000
  tier_c: 2000
session_turns_budget_tokens: 1200
compression_trigger_ratio: 0.85
max_proximity_hops: 2
relevance_weights:
  recency: 0.30
  severity: 0.20
  proximity: 0.20
  relation: 0.20
  quest: 0.10
""".strip(),
        encoding="utf-8",
    )


def test_load_llm_config_yaml_returns_typed_model_for_minimal_valid_config(tmp_path: Path) -> None:
    """Loader should parse a valid llm_config YAML file."""

    config_path = tmp_path / "llm_config.yaml"
    _write_valid_llm_config(path=config_path)

    config = load_llm_config(config_path=str(config_path))

    assert config.prompt_schema_version == "v1.4"
    assert config.tier_budget_tokens.tier_a == 4000
    assert config.relevance_weights.recency == 0.30


def test_load_llm_config_yaml_raises_validation_error_when_required_fields_missing(tmp_path: Path) -> None:
    """Loader should fail fast when required keys are absent."""

    config_path = tmp_path / "invalid_llm_config.yaml"
    config_path.write_text(
        """
prompt_schema_version: "v1.4"
compression_prompt_version: "v1.4"
tier_budget_tokens:
  tier_a: 4000
  tier_b: 3000
  tier_c: 2000
session_turns_budget_tokens: 1200
compression_trigger_ratio: 0.85
max_proximity_hops: 2
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(LLMConfigValidationError):
        load_llm_config(config_path=str(config_path))


def test_load_llm_config_yaml_rejects_unknown_fields(tmp_path: Path) -> None:
    """Loader should reject unknown keys when strict schema validation is enabled."""

    config_path = tmp_path / "llm_config_unknown_field.yaml"
    _write_valid_llm_config(path=config_path)
    config_path.write_text(
        f"{config_path.read_text(encoding='utf-8')}\nunknown_field: true\n",
        encoding="utf-8",
    )

    with pytest.raises(LLMConfigValidationError):
      load_llm_config(config_path=str(config_path))


def test_load_llm_config_yaml_raises_typed_error_on_read_failure(monkeypatch, tmp_path: Path) -> None:
    """Loader should wrap read I/O failures in a typed misconfiguration error."""

    config_path = tmp_path / "llm_config.yaml"
    _write_valid_llm_config(path=config_path)

    def _raise_os_error(*args, **kwargs):
        raise OSError("read failed")

    monkeypatch.setattr(Path, "read_text", _raise_os_error)

    with pytest.raises(LLMConfigMisconfiguredError):
        load_llm_config(config_path=str(config_path))


def test_load_llm_config_yaml_rejects_string_numbers_under_strict_mode(tmp_path: Path) -> None:
    """Loader should reject quoted numbers to avoid implicit scalar coercion."""

    config_path = tmp_path / "llm_config_string_numbers.yaml"
    config_path.write_text(
        """
prompt_schema_version: "v1.4"
compression_prompt_version: "v1.4"
tier_budget_tokens:
  tier_a: "4000"
  tier_b: 3000
  tier_c: 2000
session_turns_budget_tokens: 1200
compression_trigger_ratio: 0.85
max_proximity_hops: 2
relevance_weights:
  recency: 0.30
  severity: 0.20
  proximity: 0.20
  relation: 0.20
  quest: 0.10
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(LLMConfigValidationError):
        load_llm_config(config_path=str(config_path))
