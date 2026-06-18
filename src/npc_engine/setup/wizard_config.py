"""
Module: wizard_config
Layer: config
Purpose: Persist and load the first-run wizard configuration (LLM path choice,
         API key, model name) to/from ~/.npc_engine/wizard_config.json.
Dependencies: stdlib pathlib, json, enum; pydantic.
Used by: npc_engine.setup.path_validator; SHIP-05b Unity wizard (reads the JSON file
         directly from C#).
Does NOT: import any engine, graph, API, or scheduler layer.
Dependencies injected: config_dir parameter on load/save functions (defaults to
                       ~/.npc_engine so callers can inject a tmp_path in tests).
"""
from __future__ import annotations

import enum
import json
import pathlib

from pydantic import BaseModel

# Name of the JSON file written inside config_dir.
_CONFIG_FILENAME: str = "wizard_config.json"

# Default config directory — user home sub-directory.
_DEFAULT_CONFIG_DIR: pathlib.Path = pathlib.Path.home() / ".npc_engine"

# Default OpenAI-compatible API URL (player-supplied key path).
_DEFAULT_API_URL: str = "https://api.openai.com/v1"

# Default model for the API path (cheap, widely available).
_DEFAULT_API_MODEL: str = "gpt-4o-mini"


class LLMPath(str, enum.Enum):
    """Which LLM backend the player chose in the first-run wizard."""

    LOCAL = "local"
    API = "api"


class WizardConfig(BaseModel):
    """Persisted first-run wizard configuration.

    Attributes:
        llm_path: Which inference path the player chose (local Ollama or BYO API key).
        api_key: Player-supplied API key for path B; None when using local inference.
        api_url: OpenAI-compatible base URL for path B (e.g. OpenRouter, Together).
        api_model: Model name to request on path B.
        local_model: Ollama model tag selected for path A (e.g. ``"qwen2.5:7b"``);
                     None until a model is picked in the wizard.
    """

    llm_path: LLMPath
    api_key: str | None = None
    api_url: str = _DEFAULT_API_URL
    api_model: str = _DEFAULT_API_MODEL
    local_model: str | None = None


def load_wizard_config(
    config_dir: pathlib.Path = _DEFAULT_CONFIG_DIR,
) -> WizardConfig | None:
    """Load the wizard config from *config_dir*/wizard_config.json.

    Returns None if the file does not exist or cannot be parsed — callers should
    treat None as "wizard not yet run".

    Args:
        config_dir: Directory that contains ``wizard_config.json``. Defaults to
                    ``~/.npc_engine``; inject a tmp_path in tests.

    Returns:
        A ``WizardConfig`` instance on success, or None if the file is missing or
        contains invalid JSON / an invalid schema.
    """
    config_file = config_dir / _CONFIG_FILENAME
    if not config_file.exists():
        return None
    try:
        raw = json.loads(config_file.read_text(encoding="utf-8"))
        return WizardConfig.model_validate(raw)
    except (json.JSONDecodeError, ValueError):
        return None


def save_wizard_config(
    config: WizardConfig,
    config_dir: pathlib.Path = _DEFAULT_CONFIG_DIR,
) -> None:
    """Persist *config* to *config_dir*/wizard_config.json (creates dir if needed).

    Args:
        config: The wizard configuration to persist.
        config_dir: Directory to write ``wizard_config.json`` into. Defaults to
                    ``~/.npc_engine``; inject a tmp_path in tests.
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / _CONFIG_FILENAME
    config_file.write_text(
        config.model_dump_json(indent=2),
        encoding="utf-8",
    )
