"""
Module: llm_runtime_config
Layer: engines
Purpose: Loads and validates per-engine LLM config YAML files; enforces startup completeness.
Does NOT: select or instantiate LLM adapters.
Dependencies injected: engines.contracts.contract_models.EngineContract list via caller.
Used by: main.py (startup validation), api.dependency_singletons (singleton cache).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.engines.contracts.contract_models import EngineContract
from npc_engine.engines.llm_config_models import EngineModelConfig
from npc_engine.utils.errors import (
    EngineModelConfigMisconfiguredError,
    EngineModelConfigValidationError,
)


_ENGINES_PKG_DIR = Path(__file__).resolve().parent
_CONFIG_FILENAME = "llm_config.yaml"


def _engine_dir_from_contract_name(contract_name: str) -> str:
    """Derive the engine source directory name from a contract name.

    Convention: contract name is ``<engine>_engine``; directory is ``<engine>``.
    Example: ``dialogue_engine`` → ``dialogue``.

    Args:
        contract_name: Name field from an EngineContract.

    Returns:
        Engine directory name string.
    """
    return contract_name.removesuffix("_engine")


def _config_path_for_engine(engine_dir: str) -> Path:
    return _ENGINES_PKG_DIR / engine_dir / _CONFIG_FILENAME


def get_config(engine_name: str) -> EngineModelConfig:
    """Load and validate the per-engine LLM config for the named engine.

    The config file is expected at
    ``src/npc_engine/engines/<engine_name>/llm_config.yaml``.

    Args:
        engine_name: Engine directory name (e.g. ``"dialogue"``).

    Returns:
        Validated EngineModelConfig instance.

    Raises:
        EngineModelConfigMisconfiguredError: If the config file is missing or unreadable.
        EngineModelConfigValidationError: If the YAML is malformed or fails schema validation.
    """
    config_path = _config_path_for_engine(engine_name)

    if not config_path.exists():
        raise EngineModelConfigMisconfiguredError(
            engine=engine_name,
            config_path=str(config_path),
            detail="engine llm_config.yaml does not exist",
        )

    try:
        raw = load_yaml_mapping(
            path=config_path,
            root_error_message="engine llm config root must be a YAML object",
        )
    except (OSError, UnicodeError) as exc:
        raise EngineModelConfigMisconfiguredError(
            engine=engine_name,
            config_path=str(config_path),
            detail=str(exc),
        ) from exc
    except (ValueError, yaml.YAMLError) as exc:
        raise EngineModelConfigValidationError(
            engine=engine_name,
            config_path=str(config_path),
            detail=str(exc),
        ) from exc

    try:
        return EngineModelConfig.model_validate(raw)
    except ValidationError as exc:
        raise EngineModelConfigValidationError(
            engine=engine_name,
            config_path=str(config_path),
            detail=str(exc),
        ) from exc


def validate_all_engine_llm_configs(contracts: list[EngineContract]) -> None:
    """Assert every LLM-using engine has a valid config file; raise on first failure.

    Called once at application startup. Iterates all engine contracts whose
    ``uses_llm`` flag is True, derives the engine directory from the contract name,
    and attempts to load and validate the per-engine config.

    Args:
        contracts: All loaded EngineContract instances.

    Raises:
        EngineModelConfigMisconfiguredError: If a required config file is absent.
        EngineModelConfigValidationError: If a required config file is invalid.
    """
    for contract in contracts:
        if not contract.uses_llm:
            continue
        engine_dir = _engine_dir_from_contract_name(contract.name)
        get_config(engine_dir)
