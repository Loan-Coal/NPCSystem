"""
mock_adapter.py - Deterministic in-memory LLM adapter for tests and local runs.

Does NOT: perform external API calls.

Dependencies injected: Optional canned response payload, optional structured response payload.
"""

from typing import Any, AsyncIterator

from npc_engine.engines.llm.protocols import LLMClientProtocol


DEFAULT_RESPONSE: dict[str, Any] = {
    "npc_response": "I hear you.",
    "relation_deltas": {"trust": 0, "fear": 0, "affection": 0},
    "mood_update": None,
    "action": {"type": "speak", "target_id": None, "parameters": {}},
    "facial_expression": {"type": "neutral", "intensity": 20},
}


class MockLLMAdapter(LLMClientProtocol):
    """Deterministic adapter that always returns configured payload."""

    def __init__(
        self,
        response: dict[str, Any] | None = None,
        structured_response: dict[str, Any] | None = None,
    ) -> None:
        """Initialise adapter with optional canned response payloads.

        Args:
            response: Dict returned by generate() and stream(). Defaults to DEFAULT_RESPONSE.
            structured_response: Dict returned by generate_structured(). Defaults to response if omitted.
        """
        self._response = dict(response) if response is not None else dict(DEFAULT_RESPONSE)
        self._structured_response = (
            dict(structured_response) if structured_response is not None else dict(self._response)
        )

    async def generate(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
    ) -> str:
        """Return the npc_response string from the configured payload.

        Args:
            prompt: Ignored in mock mode.
            max_tokens: Ignored in mock mode.
            temperature: Ignored in mock mode.
            top_p: Ignored in mock mode.
            stop_sequences: Ignored in mock mode.
            system: Ignored in mock mode.

        Returns:
            str representation of _response["npc_response"], or "" if absent.
        """
        return str(self._response.get("npc_response", ""))

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Return a shallow copy of the configured structured response dict.

        Args:
            prompt: Ignored in mock mode.
            schema: Ignored in mock mode.
            max_tokens: Ignored in mock mode.
            top_p: Ignored in mock mode.
            stop_sequences: Ignored in mock mode.
            system: Ignored in mock mode.

        Returns:
            Shallow copy of the internal structured_response dict.
        """
        return dict(self._structured_response)

    async def stream(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[str]:
        """Yield whitespace-delimited tokens from the configured npc_response.

        Args:
            prompt: Ignored in mock mode.
            max_tokens: Ignored in mock mode.
            temperature: Ignored in mock mode.
            top_p: Ignored in mock mode.
            stop_sequences: Ignored in mock mode.
            system: Ignored in mock mode.

        Returns:
            Async iterator yielding each word from the npc_response with a trailing space.
        """
        text = str(self._response.get("npc_response", ""))
        for token in text.split():
            yield token + " "

    def model_name(self) -> str:
        """Return the mock model identifier.

        Returns:
            Always "mock".
        """
        return "mock"
