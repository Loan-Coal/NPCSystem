"""
prompt_builder.py - Builds dialogue prompt and system prompt from fixed context and player message.

Does NOT: call LLM adapters.

Dependencies injected: None.
"""

from __future__ import annotations

import logging
from pathlib import Path

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.engines.dialogue.dialogue_models import DialogueRequest

logger = logging.getLogger(__name__)

PROMPT_VERSION = "stage_b_v1.1"

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "prompts"
    / "dialogue"
    / "system_v1.yaml"
)


def build_system_prompt() -> str:
    """Return the static behavioral system prompt for the dialogue LLM.

    Returns:
        System prompt string loaded from prompts/dialogue/system_v1.yaml.

    Raises:
        FileNotFoundError: if the YAML file is missing.
        ValueError: if the YAML root is not a mapping.
    """
    prompt_data = load_yaml_mapping(
        _PROMPT_PATH, "prompts/dialogue/system_v1.yaml must be a mapping"
    )
    return prompt_data["system"]


def build_dialogue_prompt(request: DialogueRequest, serialized_context: str) -> str:
    """Build the deterministic dialogue prompt string for structured LLM output.

    Args:
        request: Dialogue request carrying player and NPC identifiers and message.
        serialized_context: Compact JSON context string from the context builder.

    Returns:
        Newline-delimited prompt string including version, context, and player message.
    """
    prompt = (
        f"PROMPT_VERSION={PROMPT_VERSION}\n"
        f"NPC_ID={request.npc_id}\n"
        f"PLAYER_ID={request.player_id}\n"
        f"CONTEXT={serialized_context}\n"
        f"PLAYER_MESSAGE={request.player_message}\n"
    )
    logger.debug("dialogue_prompt_assembled", extra={"prompt_version": PROMPT_VERSION, "prompt": prompt})
    return prompt
