"""
test_engine_llm_config_loader.py - Unit tests for per-engine LLM config loading and validation.

Does NOT: call live LLM services or start the application.

Dependencies injected: tmp_path fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from npc_engine.engines.contracts.contract_models import EngineContract, IdempotencyContract
from npc_engine.engines.llm_config_loader import get_config, validate_all_engine_llm_configs
from npc_engine.engines.llm_config_models import EngineModelConfig
from npc_engine.utils.errors import (
    EngineModelConfigMisconfiguredError,
    EngineModelConfigValidationError,
)


_VALID_YAML = """\
engine: dialogue
llm:
  backend: mock
  model: mock
  temperature: 0.8
  max_tokens: 512
  top_p: 0.95
  stop_sequences: []
prompt:
  name: dialogue_main
  version: 1
output_schema_ref: dialogue_response_v1
fallback:
  policy: graceful_degradation
  tiers:
    - full
    - graph_only
    - canned
timeouts_ms:
  full: 30000
  graph_only: 10000
  canned: 100
"""


def _write_engine_config(engines_dir: Path, engine_name: str, content: str) -> Path:
    engine_dir = engines_dir / engine_name
    engine_dir.mkdir(parents=True, exist_ok=True)
    config_file = engine_dir / "llm_config.yaml"
    config_file.write_text(content, encoding="utf-8")
    return config_file


def _make_llm_contract(name: str, uses_llm: bool) -> EngineContract:
    return EngineContract(
        name=name,
        version="v1.0.0",
        uses_llm=uses_llm,
        inputs=["input"],
        outputs=["output"],
        side_effects=["none"],
        idempotency=IdempotencyContract(key_required=False, replay_behavior="ignore"),
        auth_scope="graph_write",
        error_contract=["NONE"],
        tests=["test_placeholder"],
    )


# ---------------------------------------------------------------------------
# get_config — happy path
# ---------------------------------------------------------------------------


def test_get_config_returns_valid_model_for_well_formed_yaml(tmp_path: Path, monkeypatch) -> None:
    """Loader should parse a valid engine llm_config YAML into a typed model."""

    _write_engine_config(tmp_path, "dialogue", _VALID_YAML)

    import npc_engine.engines.llm_config_loader as loader_mod
    monkeypatch.setattr(loader_mod, "_ENGINES_PKG_DIR", tmp_path)

    config = get_config("dialogue")

    assert isinstance(config, EngineModelConfig)
    assert config.engine == "dialogue"
    assert config.llm.backend == "mock"
    assert config.llm.model == "mock"
    assert config.llm.temperature == 0.8
    assert config.llm.max_tokens == 512
    assert config.timeouts_ms.full == 30000
    assert config.timeouts_ms.graph_only == 10000
    assert config.fallback.policy == "graceful_degradation"
    assert config.fallback.tiers == ["full", "graph_only", "canned"]


def test_get_config_accepts_all_valid_backends(tmp_path: Path, monkeypatch) -> None:
    """Loader should accept each declared backend literal."""

    import npc_engine.engines.llm_config_loader as loader_mod
    monkeypatch.setattr(loader_mod, "_ENGINES_PKG_DIR", tmp_path)

    for backend in ("mock", "ollama", "mistral7b", "llama8b"):
        yaml_content = _VALID_YAML.replace("backend: mock", f"backend: {backend}")
        _write_engine_config(tmp_path, f"engine_{backend}", yaml_content.replace("engine: dialogue", f"engine: engine_{backend}"))
        config = get_config(f"engine_{backend}")
        assert config.llm.backend == backend


# ---------------------------------------------------------------------------
# get_config — error cases
# ---------------------------------------------------------------------------


def test_get_config_raises_misconfigured_when_file_absent(tmp_path: Path, monkeypatch) -> None:
    """Missing llm_config.yaml must raise EngineModelConfigMisconfiguredError."""

    import npc_engine.engines.llm_config_loader as loader_mod
    monkeypatch.setattr(loader_mod, "_ENGINES_PKG_DIR", tmp_path)

    with pytest.raises(EngineModelConfigMisconfiguredError) as exc_info:
        get_config("missing_engine")

    assert exc_info.value.engine == "missing_engine"
    assert "does not exist" in exc_info.value.detail


def test_get_config_raises_validation_error_for_missing_required_field(tmp_path: Path, monkeypatch) -> None:
    """YAML missing required fields must raise EngineModelConfigValidationError."""

    import npc_engine.engines.llm_config_loader as loader_mod
    monkeypatch.setattr(loader_mod, "_ENGINES_PKG_DIR", tmp_path)

    incomplete = """\
engine: dialogue
llm:
  backend: mock
  model: mock
  temperature: 0.8
  max_tokens: 512
  top_p: 0.95
  stop_sequences: []
prompt:
  name: dialogue_main
  version: 1
output_schema_ref: dialogue_response_v1
"""
    _write_engine_config(tmp_path, "dialogue", incomplete)

    with pytest.raises(EngineModelConfigValidationError) as exc_info:
        get_config("dialogue")

    assert exc_info.value.engine == "dialogue"


def test_get_config_raises_validation_error_for_unknown_field(tmp_path: Path, monkeypatch) -> None:
    """Unknown YAML keys must raise EngineModelConfigValidationError."""

    import npc_engine.engines.llm_config_loader as loader_mod
    monkeypatch.setattr(loader_mod, "_ENGINES_PKG_DIR", tmp_path)

    with_extra = _VALID_YAML + "extra_key: should_fail\n"
    _write_engine_config(tmp_path, "dialogue", with_extra)

    with pytest.raises(EngineModelConfigValidationError):
        get_config("dialogue")


def test_get_config_raises_validation_error_for_invalid_backend(tmp_path: Path, monkeypatch) -> None:
    """An unsupported backend literal must raise EngineModelConfigValidationError."""

    import npc_engine.engines.llm_config_loader as loader_mod
    monkeypatch.setattr(loader_mod, "_ENGINES_PKG_DIR", tmp_path)

    bad_backend = _VALID_YAML.replace("backend: mock", "backend: unsupported_backend")
    _write_engine_config(tmp_path, "dialogue", bad_backend)

    with pytest.raises(EngineModelConfigValidationError):
        get_config("dialogue")


def test_get_config_raises_validation_error_for_string_numbers_under_strict_mode(tmp_path: Path, monkeypatch) -> None:
    """Quoted numeric fields must be rejected under strict Pydantic mode."""

    import npc_engine.engines.llm_config_loader as loader_mod
    monkeypatch.setattr(loader_mod, "_ENGINES_PKG_DIR", tmp_path)

    quoted_int = _VALID_YAML.replace("max_tokens: 512", 'max_tokens: "512"')
    _write_engine_config(tmp_path, "dialogue", quoted_int)

    with pytest.raises(EngineModelConfigValidationError):
        get_config("dialogue")


def test_get_config_raises_misconfigured_on_io_error(tmp_path: Path, monkeypatch) -> None:
    """File read errors must surface as EngineModelConfigMisconfiguredError."""

    _write_engine_config(tmp_path, "dialogue", _VALID_YAML)

    import npc_engine.engines.llm_config_loader as loader_mod
    monkeypatch.setattr(loader_mod, "_ENGINES_PKG_DIR", tmp_path)

    def _raise(*args, **kwargs):
        raise OSError("disk failure")

    monkeypatch.setattr(Path, "read_text", _raise)

    with pytest.raises(EngineModelConfigMisconfiguredError):
        get_config("dialogue")


# ---------------------------------------------------------------------------
# validate_all_engine_llm_configs
# ---------------------------------------------------------------------------


def test_validate_all_passes_when_all_llm_engines_have_configs(tmp_path: Path, monkeypatch) -> None:
    """No exception raised when every uses_llm=True contract has a valid config."""

    import npc_engine.engines.llm_config_loader as loader_mod
    monkeypatch.setattr(loader_mod, "_ENGINES_PKG_DIR", tmp_path)

    _write_engine_config(tmp_path, "dialogue", _VALID_YAML)

    contracts = [
        _make_llm_contract("dialogue_engine", uses_llm=True),
        _make_llm_contract("quest_engine", uses_llm=False),
    ]
    validate_all_engine_llm_configs(contracts=contracts)  # must not raise


def test_validate_all_raises_when_llm_engine_config_is_missing(tmp_path: Path, monkeypatch) -> None:
    """Startup must fail when a uses_llm=True contract lacks its config file."""

    import npc_engine.engines.llm_config_loader as loader_mod
    monkeypatch.setattr(loader_mod, "_ENGINES_PKG_DIR", tmp_path)

    contracts = [_make_llm_contract("dialogue_engine", uses_llm=True)]

    with pytest.raises(EngineModelConfigMisconfiguredError):
        validate_all_engine_llm_configs(contracts=contracts)


def test_validate_all_skips_non_llm_contracts(tmp_path: Path, monkeypatch) -> None:
    """Engines with uses_llm=False are skipped even if no config file exists."""

    import npc_engine.engines.llm_config_loader as loader_mod
    monkeypatch.setattr(loader_mod, "_ENGINES_PKG_DIR", tmp_path)

    contracts = [
        _make_llm_contract("quest_engine", uses_llm=False),
        _make_llm_contract("currency_engine", uses_llm=False),
    ]
    validate_all_engine_llm_configs(contracts=contracts)  # must not raise


def test_validate_all_raises_on_invalid_config_for_llm_engine(tmp_path: Path, monkeypatch) -> None:
    """Startup must fail when a uses_llm=True contract has an invalid config file."""

    import npc_engine.engines.llm_config_loader as loader_mod
    monkeypatch.setattr(loader_mod, "_ENGINES_PKG_DIR", tmp_path)

    _write_engine_config(tmp_path, "dialogue", "not: valid: yaml: [}")

    contracts = [_make_llm_contract("dialogue_engine", uses_llm=True)]

    with pytest.raises(EngineModelConfigValidationError):
        validate_all_engine_llm_configs(contracts=contracts)


# ---------------------------------------------------------------------------
# uses_llm field in EngineContract
# ---------------------------------------------------------------------------


def test_engine_contract_defaults_uses_llm_to_false() -> None:
    """EngineContract without uses_llm field should default to False."""

    contract = _make_llm_contract("some_engine", uses_llm=False)
    assert contract.uses_llm is False


def test_engine_contract_accepts_uses_llm_true() -> None:
    """EngineContract with uses_llm: true must parse correctly."""

    contract = _make_llm_contract("dialogue_engine", uses_llm=True)
    assert contract.uses_llm is True
