"""
llm_config_loader.py - Loads and validates v1.4 llm_config YAML settings.

Does NOT: mutate runtime state or build prompt payloads.

Dependencies injected: None.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from schema.llm_config_models import LLMConfig
from utils.errors import LLMConfigMisconfiguredError, LLMConfigValidationError


def load_llm_config(config_path: str) -> LLMConfig:
    """Load llm_config file and validate it against typed Pydantic models."""

    path = Path(config_path)
    if not path.exists():
        raise LLMConfigMisconfiguredError(
            config_path=config_path,
            detail="llm config file does not exist",
        )

    try:
        raw_content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise LLMConfigMisconfiguredError(config_path=config_path, detail=str(error)) from error

    try:
        loaded: Any = yaml.safe_load(raw_content)
    except yaml.YAMLError as error:
        raise LLMConfigValidationError(config_path=config_path, detail=str(error)) from error

    if not isinstance(loaded, dict):
        raise LLMConfigValidationError(
            config_path=config_path,
            detail="llm config root must be a YAML object",
        )

    try:
        return LLMConfig.model_validate(loaded)
    except ValidationError as error:
        raise LLMConfigValidationError(config_path=config_path, detail=str(error)) from error
