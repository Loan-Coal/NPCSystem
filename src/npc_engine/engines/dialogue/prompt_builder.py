"""
Module: prompt_builder
Layer: engines
Purpose: Builds dialogue prompt and system prompt from fixed context and player message.
Does NOT: call LLM adapters or perform I/O beyond YAML loading.
Dependencies injected: None (loads YAML from _PROMPTS_DIR at module level).
Used by: npc_engine.engines.dialogue.dialogue_handler
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.engines.dialogue.dialogue_models import DialogueRequest

logger = logging.getLogger(__name__)

PROMPT_VERSION = "stage_b_v2.2"

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts" / "dialogue"
_PROMPT_PATH = _PROMPTS_DIR / "system_v1.yaml"
_VOICES_PATH = _PROMPTS_DIR / "npc_voices.yaml"

# Module-level cache so YAML is loaded once per process.
_voices_cache: dict[str, str] | None = None


def _get_voice(npc_id: str) -> str:
    """Return the voice descriptor for an NPC, falling back to _default.

    Args:
        npc_id: Stable NPC identifier.

    Returns:
        Voice descriptor string from npc_voices.yaml.
    """
    global _voices_cache
    if _voices_cache is None:
        data = load_yaml_mapping(_VOICES_PATH, "npc_voices.yaml must be a mapping")
        _voices_cache = data.get("voices", {})
    return _voices_cache.get(npc_id) or _voices_cache.get("_default", "")


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


def _extract_personal_accounts(serialized_context: str) -> list[str]:
    """Extract distorted_summary strings from npc_known_events in serialized context.

    Returns:
        Ordered list of distorted_summary strings, one per distorted event.
    """
    try:
        ctx = json.loads(serialized_context)
    except (json.JSONDecodeError, ValueError):
        return []
    accounts = []
    for item in ctx.get("npc_known_events", []):
        if isinstance(item, dict):
            ds = item.get("distorted_summary")
            if ds:
                accounts.append(ds)
    return accounts


def build_dialogue_prompt(request: DialogueRequest, serialized_context: str) -> str:
    """Build the deterministic dialogue prompt string for structured LLM output.

    Args:
        request: Dialogue request carrying player and NPC identifiers and message.
        serialized_context: Compact JSON context string from the context builder.

    Returns:
        Newline-delimited prompt string including version, context, voice, and player message.
    """
    voice = _get_voice(request.npc_id)
    accounts = _extract_personal_accounts(serialized_context)
    accounts_section = "".join(f"MY_ACCOUNT_{i}={acc}\n" for i, acc in enumerate(accounts, 1))
    prompt = (
        f"PROMPT_VERSION={PROMPT_VERSION}\n"
        f"NPC_ID={request.npc_id}\n"
        f"PLAYER_ID={request.player_id}\n"
        f"VOICE_DESCRIPTOR={voice}\n"
        + accounts_section
        + f"CONTEXT={serialized_context}\n"
        f"PLAYER_MESSAGE={request.player_message}\n"
    )
    logger.debug("dialogue_prompt_assembled", extra={"prompt_version": PROMPT_VERSION, "prompt": prompt})
    return prompt
