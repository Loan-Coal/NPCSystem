"""
response_parser.py - Validates LLM structured output into dialogue response model.
Layer: engines
Purpose: Validates LLM structured output into dialogue response model.

Does NOT: call LLM services.

Dependencies injected: None.
"""
from __future__ import annotations

from typing import Any
from npc_engine.engines.dialogue.dialogue_models import DialogueResponse


def parse_dialogue_response(payload: dict[str, Any]) -> DialogueResponse:
    """Parse and validate a raw LLM output dict into a typed DialogueResponse.

    Args:
        payload: Raw dict from LLM structured generation or fallback.

    Returns:
        Validated and frozen DialogueResponse instance.

    Raises:
        pydantic.ValidationError: If the payload does not conform to the response schema.
    """

    return DialogueResponse.model_validate(payload)
