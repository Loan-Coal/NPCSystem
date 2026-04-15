"""
mock_adapter.py - Deterministic in-memory LLM adapter for tests and local runs.

Does NOT: perform external API calls.

Dependencies injected: Optional canned response payload.
"""

from typing import Any, AsyncIterator

from engines.llm.protocols import LLMClientProtocol


DEFAULT_RESPONSE: dict[str, Any] = {
    "npc_response": "I hear you.",
    "relation_deltas": {"trust": 0, "fear": 0, "affection": 0},
    "mood_update": None,
    "action": {"type": "speak", "target_id": None, "parameters": {}},
    "facial_expression": {"type": "neutral", "intensity": 20},
}


class MockLLMAdapter(LLMClientProtocol):
    """Deterministic adapter that always returns configured payload."""

    def __init__(self, response: dict[str, Any] | None = None):
        self._response = dict(response) if response is not None else dict(DEFAULT_RESPONSE)

    async def generate(self, prompt: str, max_tokens: int, temperature: float) -> str:
        return str(self._response.get("npc_response", ""))

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
    ) -> dict[str, Any]:
        return dict(self._response)

    async def stream(self, prompt: str, max_tokens: int, temperature: float) -> AsyncIterator[str]:
        text = str(self._response.get("npc_response", ""))
        for token in text.split():
            yield token + " "

    def model_name(self) -> str:
        return "mock"
