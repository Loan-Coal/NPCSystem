"""
protocols.py - Shared protocol for LLM backend adapters.

Does NOT: implement network requests.

Dependencies injected: None.
"""

from typing import Any, AsyncIterator, Protocol, runtime_checkable


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Contract for all LLM adapter implementations."""

    async def generate(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
    ) -> str:
        """Generate plain text output.

        Args:
            prompt: Formatted prompt string to send to the backend.
            max_tokens: Maximum number of tokens to generate.
            temperature: Sampling temperature (0.0 = deterministic).
            top_p: Nucleus sampling probability mass. None means backend default.
            stop_sequences: Token sequences that halt generation. None means backend default.

        Returns:
            Generated text string from the backend.

        Raises:
            LLMTimeoutError: If the request exceeds the configured timeout.
            LLMRequestError: If the backend returns an error or invalid response.
        """

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate schema-constrained JSON output.

        Args:
            prompt: Formatted prompt string to send to the backend.
            schema: JSON schema dict constraining the output structure.
            max_tokens: Maximum number of tokens to generate.
            top_p: Nucleus sampling probability mass. None means backend default.
            stop_sequences: Token sequences that halt generation. None means backend default.

        Returns:
            Parsed dict conforming to the provided schema.

        Raises:
            LLMTimeoutError: If the request exceeds the configured timeout.
            LLMRequestError: If the backend returns an error or invalid/non-dict JSON.
        """

    def stream(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
    ) -> AsyncIterator[str]:
        """Yield streamed tokens for low-latency UX.

        Args:
            prompt: Formatted prompt string to send to the backend.
            max_tokens: Maximum number of tokens to generate.
            temperature: Sampling temperature (0.0 = deterministic).
            top_p: Nucleus sampling probability mass. None means backend default.
            stop_sequences: Token sequences that halt generation. None means backend default.

        Returns:
            Async iterator yielding token strings as they arrive.

        Raises:
            LLMTimeoutError: If the stream connection exceeds the configured timeout.
            LLMRequestError: If the backend returns a stream error.
        """

    def model_name(self) -> str:
        """Return backend model identifier.

        Returns:
            String key identifying the model (e.g. "mistral7b", "ollama").
        """
