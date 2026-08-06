"""
Module: test_run_config
Layer: test (unit)
Purpose: Unit tests for evals/run_config.py — RunConfig model and resolve_run_config().
Dependencies: pathlib, yaml, run_config (evals/, on pytest pythonpath).
Used by: pytest (make test / make check).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from run_config import RunConfig, resolve_run_config

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DIALOGUE_LLM_CONFIG = _REPO_ROOT / "src" / "npc_engine" / "engines" / "dialogue" / "llm_config.yaml"

_MINIMAL_CONFIG: dict = {
    "engine": "dialogue",
    "llm": {
        "backend": "ollama",
        "model": "test-model:7b",
        "temperature": 0.5,
        "max_tokens": 256,
        "top_p": 0.9,
        "stop_sequences": [],
    },
    "prompt": {
        "name": "dialogue_main",
        "version": 42,
    },
}


@pytest.fixture()
def tmp_llm_config(tmp_path: Path) -> Path:
    """Write a minimal llm_config.yaml to a temp directory and return its path."""
    config_path = tmp_path / "llm_config.yaml"
    config_path.write_text(yaml.dump(_MINIMAL_CONFIG), encoding="utf-8")
    return config_path


def test_resolve_reads_dialogue_llm_config() -> None:
    """resolve_run_config() returns generation_model matching llm_config.yaml's llm.model."""
    config = resolve_run_config(config_path=_DIALOGUE_LLM_CONFIG)
    expected_data = yaml.safe_load(_DIALOGUE_LLM_CONFIG.read_text(encoding="utf-8"))
    assert config.generation_model == expected_data["llm"]["model"]


def test_resolve_reads_prompt_version() -> None:
    """resolve_run_config() returns prompt_version matching llm_config.yaml's prompt.version."""
    config = resolve_run_config(config_path=_DIALOGUE_LLM_CONFIG)
    expected_data = yaml.safe_load(_DIALOGUE_LLM_CONFIG.read_text(encoding="utf-8"))
    assert config.prompt_version == str(expected_data["prompt"]["version"])


def test_git_sha_is_seven_chars() -> None:
    """resolve_run_config() includes a non-empty 7-char git SHA."""
    config = resolve_run_config(config_path=_DIALOGUE_LLM_CONFIG)
    assert len(config.git_sha) == 7
    assert config.git_sha.strip()


def test_run_config_is_frozen(tmp_llm_config: Path) -> None:
    """RunConfig is immutable — setattr raises ValidationError (Pydantic frozen model)."""
    config = resolve_run_config(config_path=tmp_llm_config)
    with pytest.raises(Exception):
        setattr(config, "generation_model", "other")


def test_seed_field_absent() -> None:
    """RunConfig has no seed field — LLMGenerateProtocol.generate() has no seed param."""
    assert "seed" not in RunConfig.model_fields


def test_resolve_with_custom_profile_and_version(tmp_llm_config: Path) -> None:
    """resolve_run_config() forwards retrieval_profile and golden_set_version."""
    config = resolve_run_config(
        config_path=tmp_llm_config,
        retrieval_profile="strict",
        golden_set_version="v2",
    )
    assert config.retrieval_profile == "strict"
    assert config.golden_set_version == "v2"


def test_run_config_fields_from_minimal_yaml(tmp_llm_config: Path) -> None:
    """resolve_run_config() correctly maps all llm YAML fields to RunConfig attributes."""
    config = resolve_run_config(config_path=tmp_llm_config)
    assert config.generation_model == "test-model:7b"
    assert config.temperature == 0.5
    assert config.max_tokens == 256
    assert config.top_p == 0.9
    assert config.prompt_version == "42"
