"""
Module: test_run_config
Layer: test (unit)
Purpose: Unit tests for evals/run_config.py — RunConfig model and resolve_run_config().
Dependencies: pathlib, yaml, run_config (evals/, on pytest pythonpath).
Used by: pytest (make test / make check).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
import yaml

from run_config import GoldenSetVersionError, RunConfig, resolve_golden_set_version, resolve_run_config

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


def test_resolve_with_custom_retrieval_profile(tmp_path: Path, tmp_llm_config: Path) -> None:
    """resolve_run_config() forwards retrieval_profile; golden_set_version is computed from cases_dir."""
    case_file = tmp_path / "case.yaml"
    case_file.write_text("prompt: hello", encoding="utf-8")
    config = resolve_run_config(
        config_path=tmp_llm_config,
        retrieval_profile="strict",
        cases_dir=tmp_path,
    )
    assert config.retrieval_profile == "strict"
    assert len(config.golden_set_version) == 12


def test_run_config_fields_from_minimal_yaml(tmp_llm_config: Path) -> None:
    """resolve_run_config() correctly maps all llm YAML fields to RunConfig attributes."""
    config = resolve_run_config(config_path=tmp_llm_config)
    assert config.generation_model == "test-model:7b"
    assert config.temperature == 0.5
    assert config.max_tokens == 256
    assert config.top_p == 0.9
    assert config.prompt_version == "42"


# ---------------------------------------------------------------------------
# EVAL-P1.5: honest golden_set_version
# ---------------------------------------------------------------------------


def test_golden_set_version_changes_when_a_case_changes(tmp_path: Path, tmp_llm_config: Path) -> None:
    """golden_set_version is content-derived — editing a case file changes the version."""
    case_file = tmp_path / "case_001.yaml"
    case_file.write_text("prompt: hello", encoding="utf-8")

    config_before = resolve_run_config(config_path=tmp_llm_config, cases_dir=tmp_path)

    case_file.write_text("prompt: world", encoding="utf-8")

    config_after = resolve_run_config(config_path=tmp_llm_config, cases_dir=tmp_path)

    assert config_before.golden_set_version != config_after.golden_set_version


def test_golden_set_version_stable_across_mtime_change(tmp_path: Path) -> None:
    """golden_set_version does not change when only a file's mtime changes."""
    case_file = tmp_path / "case.yaml"
    case_file.write_text("prompt: hello", encoding="utf-8")

    v1 = resolve_golden_set_version(tmp_path)

    # advance mtime by 5 seconds without touching content
    future = time.time() + 5
    os.utime(case_file, (future, future))

    v2 = resolve_golden_set_version(tmp_path)

    assert v1 == v2


def test_golden_set_version_error_on_empty_dir(tmp_path: Path) -> None:
    """resolve_golden_set_version raises GoldenSetVersionError when the directory is empty."""
    with pytest.raises(GoldenSetVersionError):
        resolve_golden_set_version(tmp_path)


def test_golden_set_version_error_on_missing_dir(tmp_path: Path) -> None:
    """resolve_golden_set_version raises GoldenSetVersionError when the directory is missing."""
    missing = tmp_path / "nonexistent"
    with pytest.raises(GoldenSetVersionError):
        resolve_golden_set_version(missing)


def test_golden_set_version_is_12_hex_chars(tmp_path: Path) -> None:
    """resolve_golden_set_version returns a 12-character lowercase hex string."""
    (tmp_path / "case.yaml").write_text("a: 1", encoding="utf-8")
    version = resolve_golden_set_version(tmp_path)
    assert len(version) == 12
    assert all(c in "0123456789abcdef" for c in version)
