"""Tests for npc_engine.setup.wizard_config — config persistence."""
from __future__ import annotations

import json
import pathlib

import pytest

from npc_engine.setup.wizard_config import (
    LLMPath,
    WizardConfig,
    load_wizard_config,
    save_wizard_config,
)


class TestLLMPath:
    def test_local_value(self) -> None:
        assert LLMPath.LOCAL == "local"

    def test_api_value(self) -> None:
        assert LLMPath.API == "api"


class TestWizardConfigModel:
    def test_local_path_minimal(self) -> None:
        cfg = WizardConfig(llm_path=LLMPath.LOCAL)
        assert cfg.llm_path == LLMPath.LOCAL
        assert cfg.api_key is None

    def test_api_path_with_key(self) -> None:
        cfg = WizardConfig(llm_path=LLMPath.API, api_key="sk-test")
        assert cfg.llm_path == LLMPath.API
        assert cfg.api_key == "sk-test"

    def test_defaults_populated(self) -> None:
        cfg = WizardConfig(llm_path=LLMPath.API)
        assert cfg.api_url.startswith("https://")
        assert cfg.api_model != ""

    def test_local_model_field(self) -> None:
        cfg = WizardConfig(llm_path=LLMPath.LOCAL, local_model="qwen2.5:7b")
        assert cfg.local_model == "qwen2.5:7b"


class TestLoadWizardConfig:
    def test_returns_none_when_file_missing(self, tmp_path: pathlib.Path) -> None:
        result = load_wizard_config(config_dir=tmp_path)
        assert result is None

    def test_returns_config_when_file_exists(self, tmp_path: pathlib.Path) -> None:
        payload = {
            "llm_path": "local",
            "api_key": None,
            "api_url": "https://api.openai.com/v1",
            "api_model": "gpt-4o-mini",
            "local_model": "qwen2.5:7b",
        }
        (tmp_path / "wizard_config.json").write_text(json.dumps(payload))
        result = load_wizard_config(config_dir=tmp_path)
        assert result is not None
        assert result.llm_path == LLMPath.LOCAL
        assert result.local_model == "qwen2.5:7b"

    def test_returns_none_on_corrupted_json(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "wizard_config.json").write_text("not-json{{{")
        result = load_wizard_config(config_dir=tmp_path)
        assert result is None


class TestSaveWizardConfig:
    def test_creates_file_and_directory(self, tmp_path: pathlib.Path) -> None:
        nested = tmp_path / "nested"
        cfg = WizardConfig(llm_path=LLMPath.LOCAL, local_model="qwen2.5:3b")
        save_wizard_config(cfg, config_dir=nested)
        assert (nested / "wizard_config.json").exists()

    def test_roundtrip_local(self, tmp_path: pathlib.Path) -> None:
        cfg = WizardConfig(llm_path=LLMPath.LOCAL, local_model="qwen2.5:7b")
        save_wizard_config(cfg, config_dir=tmp_path)
        loaded = load_wizard_config(config_dir=tmp_path)
        assert loaded is not None
        assert loaded.llm_path == LLMPath.LOCAL
        assert loaded.local_model == "qwen2.5:7b"

    def test_roundtrip_api(self, tmp_path: pathlib.Path) -> None:
        cfg = WizardConfig(
            llm_path=LLMPath.API,
            api_key="sk-secret",
            api_url="https://openrouter.ai/api/v1",
            api_model="gpt-4o",
        )
        save_wizard_config(cfg, config_dir=tmp_path)
        loaded = load_wizard_config(config_dir=tmp_path)
        assert loaded is not None
        assert loaded.llm_path == LLMPath.API
        assert loaded.api_key == "sk-secret"
        assert loaded.api_url == "https://openrouter.ai/api/v1"
        assert loaded.api_model == "gpt-4o"

    def test_overwrites_existing_file(self, tmp_path: pathlib.Path) -> None:
        cfg1 = WizardConfig(llm_path=LLMPath.LOCAL, local_model="qwen2.5:3b")
        cfg2 = WizardConfig(llm_path=LLMPath.API, api_key="sk-new")
        save_wizard_config(cfg1, config_dir=tmp_path)
        save_wizard_config(cfg2, config_dir=tmp_path)
        loaded = load_wizard_config(config_dir=tmp_path)
        assert loaded is not None
        assert loaded.llm_path == LLMPath.API
