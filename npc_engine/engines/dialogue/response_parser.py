"""
response_parser.py - Validates LLM structured output into dialogue response model.

Does NOT: call LLM services.

Dependencies injected: None.
"""

from api.schemas import DialogueResponse


def parse_dialogue_response(payload: dict) -> DialogueResponse:
    """Parse and validate raw LLM dict into typed response model."""

    return DialogueResponse.model_validate(payload)
