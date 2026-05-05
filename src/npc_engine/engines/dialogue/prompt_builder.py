"""
prompt_builder.py - Builds dialogue prompt from fixed context and player message.

Does NOT: call LLM adapters.

Dependencies injected: None.
"""

from npc_engine.engines.dialogue.dialogue_models import DialogueRequest


PROMPT_VERSION = "stage_b_v1.0"


def build_dialogue_prompt(request: DialogueRequest, serialized_context: str) -> str:
    """Build the deterministic dialogue prompt string for structured LLM output.

    Args:
        request: Dialogue request carrying player and NPC identifiers and message.
        serialized_context: Compact JSON context string from the context builder.

    Returns:
        Newline-delimited prompt string including version, instructions, and context.
    """

    return (
        f"PROMPT_VERSION={PROMPT_VERSION}\n"
        "INSTRUCTIONS: Respond with JSON matching required schema only.\n"
        f"NPC_ID={request.npc_id}\n"
        f"PLAYER_ID={request.player_id}\n"
        f"CONTEXT={serialized_context}\n"
        f"PLAYER_MESSAGE={request.player_message}\n"
    )
