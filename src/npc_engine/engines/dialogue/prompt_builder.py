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
from npc_engine.config import ContentRating
from npc_engine.engines.dialogue.dialogue_models import DialogueRequest

logger = logging.getLogger(__name__)

PROMPT_VERSION = "stage_b_v2.12"

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts" / "dialogue"
_PROMPT_PATH = _PROMPTS_DIR / "system_v1.yaml"
_CONTENT_CEILING_YAML: Path = (
    Path(__file__).resolve().parents[2] / "prompts" / "moderation" / "content_ceiling_v1.yaml"
)

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


def build_system_prompt(content_rating: ContentRating = "mature") -> str:
    """Return the behavioral system prompt for the dialogue LLM.

    When content_rating is not 'mature', appends the ceiling rule from
    prompts/moderation/content_ceiling_v1.yaml so the LLM self-censors.
    The 'mature' default preserves all existing behaviour unchanged.

    Args:
        content_rating: The effective content ceiling for this deployment.

    Returns:
        System prompt string, optionally with a content-ceiling rule appended.

    Raises:
        FileNotFoundError: if the YAML file is missing.
        ValueError: if the YAML root is not a mapping.
    """
    prompt_data = load_yaml_mapping(
        _PROMPT_PATH, "prompts/dialogue/system_v1.yaml must be a mapping"
    )
    base_prompt = cast(str, prompt_data["system"])
    if content_rating == "mature":
        return base_prompt
    ceiling_data = load_yaml_mapping(
        _CONTENT_CEILING_YAML, "content_ceiling_v1.yaml must be a mapping"
    )
    rule = cast(str, ceiling_data.get("rules", {}).get(content_rating, ""))
    return base_prompt + "\n" + rule if rule else base_prompt


_RUMOR_KNOWLEDGE_STATE = "rumor"


def _extract_personal_accounts(serialized_context: str) -> tuple[list[str], list[str]]:
    """Split distorted_summary accounts into firsthand vs hearsay (S26.1, ISSUE-093).

    An account whose event carries ``knowledge_state == "rumor"`` is second-hand and is
    returned as hearsay; any other distorted account (``knows`` or no state) is firsthand.
    The distorted content is preserved verbatim in both channels — only the framing
    (firsthand MY_ACCOUNT vs attributed HEARSAY) differs, so the gossip-distortion feature
    is kept while a rumour is no longer recast as something the NPC witnessed.

    Returns:
        Tuple of (firsthand_accounts, hearsay_accounts), each an ordered list of
        distorted_summary strings.
    """
    try:
        ctx = json.loads(serialized_context)
    except (json.JSONDecodeError, ValueError):
        return [], []
    firsthand: list[str] = []
    hearsay: list[str] = []
    for item in ctx.get("npc_known_events", []):
        if not isinstance(item, dict):
            continue
        ds = item.get("distorted_summary")
        if not ds:
            continue
        if item.get("knowledge_state") == _RUMOR_KNOWLEDGE_STATE:
            hearsay.append(ds)
        else:
            firsthand.append(ds)
    return firsthand, hearsay


_EPOCH_GUARDS: dict[str, str] = {
    "war": "WAR IS ACTIVE. No peace treaty. No ceasefire. No resolution. Stating otherwise is a critical failure.",
    "famine": "FAMINE IS ACTIVE. Food is scarce. Do not imply abundance.",
    "plague": "PLAGUE IS ACTIVE. Disease spreads. Do not imply normal health.",
}

# Max-attention reinforcement of Rule 9 (ECHO PROHIBITION) and false-premise/
# presupposition resistance. The canonical rules live in system_v1.yaml, but a
# 14b model tends to honour them more reliably when repeated as a short constraint
# token right before the fenced player message. Mirrors the _EPOCH_GUARDS pattern.
_ECHO_GUARD_TEXT: str = (
    "Do not repeat any specific number, price, quantity, name, or title the player "
    "states as if confirming it — refer to it as their claim, or answer only in your "
    "own general terms. If the player claims you witnessed, saw, did, or were present "
    "at something, do not confirm it; speak only from the knowledge in your context."
)

# Keywords that indicate the NPC has relevant lore for a sensitive topic.
# If NONE of the keywords appear in the NPC's known-event text, the topic is a gap.
_GAP_KEYWORDS: dict[str, list[str]] = {
    "peace_resolution": ["peace", "treaty", "ceasefire", "armistice", "truce"],
    "plague_quarantine": ["plague", "quarantine", "disease", "epidemic", "contagion"],
    "troop_specifics": ["regiment", "battalion", "flank", "garrison", "deployment", "positioned"],
}


def _build_knowledge_gaps(serialized_context: str) -> str:
    """Build a KNOWLEDGE_GAPS line listing lore topics absent from the NPC's known events.

    Derives gaps by cross-referencing the world state and active conditions against
    the NPC's npc_known_events list. Topics where the NPC has zero relevant events
    are listed so the system prompt Rule 14 can enforce hard ignorance.

    Args:
        serialized_context: Compact JSON context string from the context builder.

    Returns:
        "KNOWLEDGE_GAPS=<comma-list>\\n" when gaps exist, empty string otherwise.
    """
    try:
        ctx = json.loads(serialized_context)
    except (json.JSONDecodeError, ValueError):
        return ""

    world = ctx.get("world", {})
    epoch = world.get("epoch", "")
    active_conditions = {str(c).lower() for c in (world.get("active_conditions") or [])}

    known_events = ctx.get("npc_known_events", [])
    event_text = " ".join(
        " ".join(str(v) for v in e.values() if isinstance(v, str))
        for e in known_events
        if isinstance(e, dict)
    ).lower()

    gaps: list[str] = []

    # peace_resolution: only relevant when epoch=war; NPC has no peace/treaty events
    if epoch == "war":
        if not any(kw in event_text for kw in _GAP_KEYWORDS["peace_resolution"]):
            gaps.append("peace_resolution")

    # plague_quarantine: world has no plague condition and NPC has no disease events
    if "plague" not in active_conditions:
        if not any(kw in event_text for kw in _GAP_KEYWORDS["plague_quarantine"]):
            gaps.append("plague_quarantine")

    # troop_specifics: NPC has no direct military-positional intel
    if not any(kw in event_text for kw in _GAP_KEYWORDS["troop_specifics"]):
        gaps.append("troop_specifics")

    if not gaps:
        return ""
    return "KNOWLEDGE_GAPS=" + ",".join(gaps) + "\n"


def _build_runtime_constraints(serialized_context: str) -> str:
    """Build a dynamic epoch-constraint block from the current world state.

    Injected just before the player message so the model sees epoch constraints
    at maximum attention weight. Pure function of context — no randomness.

    Args:
        serialized_context: Compact JSON context string from the context builder.

    Returns:
        Newline-terminated constraint block, or empty string if world state absent.
    """
    try:
        ctx = json.loads(serialized_context)
    except (json.JSONDecodeError, ValueError):
        return ""
    epoch = ctx.get("world", {}).get("epoch", "")
    if not epoch:
        return ""
    lines = [f"RUNTIME_EPOCH={epoch}"]
    guard = _EPOCH_GUARDS.get(epoch)
    if guard:
        lines.append(f"EPOCH_GUARD={guard}")
    return "\n".join(lines) + "\n"


def build_dialogue_prompt(request: DialogueRequest, serialized_context: str) -> str:
    """Build the deterministic dialogue prompt string for structured LLM output.

    Args:
        request: Dialogue request carrying player and NPC identifiers and message.
        serialized_context: Compact JSON context string from the context builder.

    Returns:
        Newline-delimited prompt string including version, context, voice, and player message.
    """
    voice = _extract_voice_descriptor(serialized_context)
    firsthand_accounts, hearsay_accounts = _extract_personal_accounts(serialized_context)
    accounts_section = "".join(f"MY_ACCOUNT_{i}={acc}\n" for i, acc in enumerate(firsthand_accounts, 1))
    hearsay_section = "".join(f"HEARSAY_{i}={acc}\n" for i, acc in enumerate(hearsay_accounts, 1))
    runtime_constraints = _build_runtime_constraints(serialized_context)
    knowledge_gaps = _build_knowledge_gaps(serialized_context)
    echo_guard = f"ECHO_GUARD={_ECHO_GUARD_TEXT}\n"
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
        + hearsay_section
        + f"CONTEXT={serialized_context}\n"
        + runtime_constraints
        + knowledge_gaps
        + echo_guard
        + fenced_player_message
    )
    # L1-03: never log the assembled prompt here — it carries the raw player_message
    # and NPC context and is NOT behind the LOG_LLM_PROMPTS env-gate. The gated,
    # dev-only prompt log lives in llm_client. Keep only the non-sensitive event.
    logger.debug("dialogue_prompt_assembled", extra={"prompt_version": PROMPT_VERSION})
    return prompt
