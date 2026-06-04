"""
mock_adapter.py - Deterministic in-memory LLM adapter for tests and local runs.

Does NOT: perform external API calls.

Dependencies injected: Optional canned response payload, optional structured response payload.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from npc_engine.engines.llm.protocols import LLMClientProtocol


DEFAULT_RESPONSE: dict[str, Any] = {
    "npc_response": "I hear you.",
    "relation_deltas": {"trust": 0, "fear": 0, "affection": 0},
    "mood_update": None,
    "action": {"type": "speak", "target_id": None, "parameters": {}},
    "facial_expression": {"type": "neutral", "intensity": 20},
}

_GARBAGE_RESPONSE: dict[str, Any] = {"__garbage__": True}


class MockLLMAdapter(LLMClientProtocol):
    """Deterministic adapter that always returns configured payload.

    Supports four fault-injection modes via keyword-only constructor flags:

    - ``raise_on_generate=<exception>``: every call to ``generate()`` raises the
      given exception instance or class. Used to test the fallback contract.
      Does NOT affect ``generate_structured()``.
    - ``fail_first_call=True``: raises ``ValidationError`` on the first call to
      ``generate_structured``, then returns the normal payload on subsequent calls.
      Used to verify that the one-repair-retry path succeeds.
    - ``return_garbage=True``: every call to ``generate_structured`` returns
      ``{"__garbage__": True}``, which will fail Pydantic validation. Used to
      verify that both retry attempts fail and the canned fallback is served.
    - Neither flag set (default): always returns the configured payload.
    """

    def __init__(
        self,
        response: dict[str, Any] | None = None,
        structured_response: dict[str, Any] | None = None,
        *,
        raise_on_generate: type[Exception] | Exception | None = None,
        fail_first_call: bool = False,
        return_garbage: bool = False,
    ) -> None:
        """Initialise adapter with optional canned response payloads and fault-injection flags.

        Args:
            response: Dict returned by generate() and stream(). Defaults to DEFAULT_RESPONSE.
            structured_response: Dict returned by generate_structured(). Defaults to response.
            raise_on_generate: When set, every call to ``generate()`` raises this exception.
                May be an exception *class* (raised as ``raise_on_generate("mock-error")``)
                or an exception *instance* (re-raised directly). Mutually exclusive with
                return_garbage.
            fail_first_call: When True, raise ValidationError on the first generate_structured
                call only. Subsequent calls return the normal structured_response. Mutually
                exclusive with return_garbage.
            return_garbage: When True, every generate_structured call returns a dict that fails
                Pydantic validation (``{"__garbage__": True}``). Mutually exclusive with
                fail_first_call and raise_on_generate.

        Raises:
            ValueError: If mutually exclusive flags are combined.
        """
        mutual_excl_flags = sum([
            raise_on_generate is not None,
            fail_first_call,
            return_garbage,
        ])
        if mutual_excl_flags > 1:
            raise ValueError(
                "raise_on_generate, fail_first_call, and return_garbage are mutually exclusive"
            )
        self._response = dict(response) if response is not None else dict(DEFAULT_RESPONSE)
        self._structured_response = (
            dict(structured_response) if structured_response is not None else dict(self._response)
        )
        self._raise_on_generate = raise_on_generate
        self._fail_first_call = fail_first_call
        self._return_garbage = return_garbage
        self._call_count = 0

    async def close(self) -> None:
        """No-op — mock adapter has no external resources to release."""

    async def health_check(self) -> bool:
        """Return True — mock adapter is always ready. Non-raising.

        Returns:
            Always True.
        """
        return True

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

        Raises:
            raise_on_generate: If that flag was set at construction.
        """
        if self._raise_on_generate is not None:
            exc = self._raise_on_generate
            if isinstance(exc, type):
                raise exc("mock-generate-error")
            raise exc
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

        When ``return_garbage=True`` was passed at construction, returns a dict
        that will fail Pydantic validation on every call.  When ``fail_first_call=True``
        was passed, raises ``ValidationError`` on the first call only.

        Args:
            prompt: Ignored in mock mode.
            schema: Ignored in mock mode.
            max_tokens: Ignored in mock mode.
            top_p: Ignored in mock mode.
            stop_sequences: Ignored in mock mode.
            system: Ignored in mock mode.

        Returns:
            Shallow copy of the internal structured_response dict (or garbage dict).

        Raises:
            ValidationError: On the first call when fail_first_call=True.
        """
        self._call_count += 1
        if self._return_garbage:
            return dict(_GARBAGE_RESPONSE)
        if self._fail_first_call and self._call_count == 1:
            from pydantic import BaseModel

            class _Stub(BaseModel):
                x: int

            _Stub.model_validate({"x": "not-an-int"})  # always raises ValidationError
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
