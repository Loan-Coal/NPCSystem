"""
llm_schema_loader.py - Loads and validates v1.4 llm_config YAML settings.
Layer: config
Purpose: (auto-detected — review)

Does NOT: mutate runtime state or build prompt payloads.

Dependencies injected: None.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.utils.errors import LLMConfigMisconfiguredError, LLMConfigValidationError


def load_llm_config(config_path: str) -> LLMConfig:
    """Load llm_config file and validate it against typed Pydantic models.

    Args:
        config_path: str — filesystem path to the llm_config YAML file.

    Returns:
        Validated LLMConfig instance.

    Raises:
        LLMConfigMisconfiguredError: if the file does not exist or cannot be read.
        LLMConfigValidationError: if the YAML root is not a mapping, the YAML is malformed,
            or the Pydantic validation fails.
    """

    path = Path(config_path)
    if not path.exists():
        raise LLMConfigMisconfiguredError(
            config_path=config_path,
            detail="llm config file does not exist",
        )

    try:
        loaded = load_yaml_mapping(path=path, root_error_message="llm config root must be a YAML object")
    except (OSError, UnicodeError) as error:
        raise LLMConfigMisconfiguredError(config_path=config_path, detail=str(error)) from error
    except (ValueError, yaml.YAMLError) as error:
        raise LLMConfigValidationError(config_path=config_path, detail=str(error)) from error

    try:
        return LLMConfig.model_validate(loaded)
    except ValidationError as error:
        raise LLMConfigValidationError(config_path=config_path, detail=str(error)) from error
