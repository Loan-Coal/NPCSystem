"""
Module: prompt_builder_standing
Layer: engines
Purpose: Derive the STANDING tone line for the dialogue prompt from player relation scalars.
Does NOT: call the LLM, perform I/O, or mutate state — a pure string transform.
Dependencies injected: None (pure function over json + derive_standing).
Used by: npc_engine.engines.dialogue.prompt_builder.build_dialogue_prompt
"""

from __future__ import annotations

import json

from npc_engine.engines.relationship.standing import derive_standing


def build_standing_line(serialized_context: str) -> str:
    """Derive the ``STANDING=<band>`` prompt line from the player relation scalars.

    Reads ``player_relation.trust/fear/affection`` from the serialized context JSON
    and passes them to ``derive_standing``. Returns an empty string when the relation
    edge or any scalar is absent, so the line is silently omitted.

    Args:
        serialized_context: Compact JSON context string from the context builder.
    Returns:
        ``"STANDING=<band>\\n"`` when all three scalars are present, ``""`` otherwise.
    """
    try:
        ctx = json.loads(serialized_context)
    except (json.JSONDecodeError, ValueError):
        return ""
    relation = ctx.get("player_relation")
    if not isinstance(relation, dict):
        return ""
    trust = relation.get("trust")
    fear = relation.get("fear")
    affection = relation.get("affection")
    if trust is None or fear is None or affection is None:
        return ""
    band = derive_standing(trust=int(trust), fear=int(fear), affection=int(affection))
    return f"STANDING={band.value}\n"
