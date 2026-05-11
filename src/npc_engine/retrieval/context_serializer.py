"""
context_serializer.py - Deterministically serializes merged context items.

Does NOT: enforce token budget or merge tiers.

Dependencies injected: None.
"""

import json
from typing import Any

from npc_engine.retrieval.context_merger import MergedContext
from npc_engine.retrieval.context_utils import serialize_json


def _safe_parse(text: str) -> Any:
    """Parse serialized dict/list text to JSON-compatible structure."""

    try:
        return json.loads(text)
    except ValueError:
        return text


def _extract_items(context: MergedContext) -> dict[str, str]:
    """Map context items by key for fixed skeleton assembly."""

    return {item.key: item.text for item in context.items}


def _extract_character_profile(context: MergedContext) -> Any:
    """Extract NPC character payload from tier-A character keys."""

    for item in context.items:
        if item.key.startswith("character:"):
            return _safe_parse(item.text)
    return {}



def serialize_context(context: MergedContext) -> str:
    """Serialize merged context into a fixed-schema JSON string for prompt injection.

    Extracts well-known keys (world, emotion, character, location, relation:player,
    nearby_npcs, session, events, rag) from the context items and assembles them
    into a canonical skeleton structure.

    Args:
        context: Merged and budget-enforced context to serialize.

    Returns:
        Compact JSON string with sorted keys suitable for prompt injection.
    """

    mapped = _extract_items(context=context)
    known_events = [_safe_parse(item.text) for item in context.items if item.key.startswith("event:")]
    rag_events = [_safe_parse(item.text) for item in context.items if item.key.startswith("rag:")]
    character_payload = _extract_character_profile(context=context)
    relation_payload = _safe_parse(mapped.get("relation:player", "{}"))
    nearby_payload = _safe_parse(mapped.get("nearby_npcs", "[]"))
    location_payload: Any = next(
        (
            _safe_parse(item.text)
            for item in context.items
            if item.key.startswith("location:")
        ),
        {},
    )
    emotion_payload = _safe_parse(mapped.get("emotion", "{}"))
    world_payload = _safe_parse(mapped.get("world", "{}"))
    session_payload = _safe_parse(mapped.get("session", "[]"))

    npc_profile = character_payload if isinstance(character_payload, dict) else {}
    if isinstance(location_payload, dict) and "name" in location_payload:
        npc_profile = {
            **npc_profile,
            "current_location": location_payload.get("name"),
        }

    reputation_payload = _safe_parse(mapped.get("reputation", "[]"))

    skeleton = {
        "world": world_payload if isinstance(world_payload, dict) else {},
        "npc": {
            "profile": npc_profile,
            "emotion": emotion_payload if isinstance(emotion_payload, dict) else {},
        },
        "player_reputation": reputation_payload if isinstance(reputation_payload, list) else [],
        "player_relation": relation_payload if isinstance(relation_payload, dict) else {},
        "npc_known_events": [*known_events, *rag_events],
        "nearby_npcs": nearby_payload if isinstance(nearby_payload, list) else [],
        "recent_session_turns": session_payload if isinstance(session_payload, list) else [],
    }
    return serialize_json(skeleton, compact=True)
