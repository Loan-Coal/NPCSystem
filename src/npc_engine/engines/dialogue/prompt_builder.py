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
from typing import cast

from npc_engine.common.yaml_utils import load_yaml_mapping
from npc_engine.engines.dialogue.dialogue_models import DialogueRequest

logger = logging.getLogger(__name__)

PROMPT_VERSION = "stage_b_v2.8"

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts" / "dialogue"
_PROMPT_PATH = _PROMPTS_DIR / "system_v1.yaml"

# Sentinels that fence untrusted player input (L1-05). The system prompt instructs
# the model that anything between these markers is player speech, never an
# instruction or a lore source. Sanitization strips forged markers and collapses
# newlines so a player cannot inject a forged KEY=VALUE prompt line.
_PLAYER_MESSAGE_OPEN = "<<<PLAYER_MESSAGE>>>"
_PLAYER_MESSAGE_CLOSE = "<<<END_PLAYER_MESSAGE>>>"


def _sanitize_player_message(message: str) -> str:
    """Neutralize prompt-injection vectors in raw player input (L1-05).

    Removes any forged sentinel markers and collapses CR/LF so a player cannot
    break out of the fenced region to inject a new prompt field (e.g. a forged
    ``MY_ACCOUNT_1=`` or ``CONTEXT=`` line). The model still receives the player's
    words verbatim, just on a single fenced line.

    Args:
        message: Raw, already length-capped player message.
    Returns:
        Sanitized single-line message safe to embed between the sentinels.
    """
    cleaned = message.replace(_PLAYER_MESSAGE_OPEN, "").replace(_PLAYER_MESSAGE_CLOSE, "")
    return cleaned.replace("\r", " ").replace("\n", " ")


def _extract_voice_descriptor(serialized_context: str) -> str:
    """Return the voice descriptor for the NPC from the serialized context.

    Reads voice_descriptor from npc.profile in the context JSON. Returns empty
    string when absent or when the context is malformed.

    Args:
        serialized_context: Compact JSON context string from the context builder.

    Returns:
        Voice descriptor string, or empty string if not present.
    """
    try:
        ctx = json.loads(serialized_context)
    except (json.JSONDecodeError, ValueError):
        return ""
    return ctx.get("npc", {}).get("profile", {}).get("voice_descriptor") or ""


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
    return cast(str, prompt_data["system"])


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
    voice = _extract_voice_descriptor(serialized_context)
    accounts = _extract_personal_accounts(serialized_context)
    accounts_section = "".join(f"MY_ACCOUNT_{i}={acc}\n" for i, acc in enumerate(accounts, 1))
    fenced_player_message = (
        f"{_PLAYER_MESSAGE_OPEN}\n"
        f"{_sanitize_player_message(request.player_message)}\n"
        f"{_PLAYER_MESSAGE_CLOSE}\n"
    )
    prompt = (
        f"PROMPT_VERSION={PROMPT_VERSION}\n"
        f"NPC_ID={request.npc_id}\n"
        f"PLAYER_ID={request.player_id}\n"
        f"VOICE_DESCRIPTOR={voice}\n"
        + accounts_section
        + f"CONTEXT={serialized_context}\n"
        + fenced_player_message
    )
    # L1-03: never log the assembled prompt here — it carries the raw player_message
    # and NPC context and is NOT behind the LOG_LLM_PROMPTS env-gate. The gated,
    # dev-only prompt log lives in llm_client. Keep only the non-sensitive event.
    logger.debug("dialogue_prompt_assembled", extra={"prompt_version": PROMPT_VERSION})
    return prompt
