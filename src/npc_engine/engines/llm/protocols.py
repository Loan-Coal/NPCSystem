"""
Module: protocols
Layer: engines
Purpose: ISP-split Protocols for LLM backend adapters (SEV-23 / DEC-121) — generate,
         structured, and stream surfaces so a backend implements only what it supports.
Does NOT: implement network requests.
Dependencies injected: None.
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Protocol, runtime_checkable


@runtime_checkable
class LLMGenerateProtocol(Protocol):
    """Minimal LLM contract: plain-text generation plus introspection.

    The smallest surface most engines need (chapter, memory-consolidation,
    proactive, …). A backend that only does text generation implements just this.
    """

    async def generate(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
    ) -> str:
        """Generate plain text output.

        Args:
            prompt: Formatted prompt string to send to the backend.
            max_tokens: Maximum number of tokens to generate.
            temperature: Sampling temperature (0.0 = deterministic).
            top_p: Nucleus sampling probability mass. None means backend default.
            stop_sequences: Token sequences that halt generation. None means backend default.
            system: Optional system prompt injected via the backend's system channel.

        Returns:
            Generated text string from the backend.

        Raises:
            LLMTimeoutError: If the request exceeds the configured timeout.
            LLMRequestError: If the backend returns an error or invalid response.
        """

    async def health_check(self) -> bool:
        """Return True if the backend is reachable and ready. Non-raising.

        Returns:
            True if the backend responded successfully, False on any error.
        """

    def model_name(self) -> str:
        """Return backend model identifier.

        Returns:
            String key identifying the model (e.g. "mistral7b", "ollama").
        """


@runtime_checkable
class LLMStructuredProtocol(LLMGenerateProtocol, Protocol):
    """Adds schema-constrained JSON generation (e.g. quest generation, dialogue)."""

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Generate schema-constrained JSON output.

        Args:
            prompt: Formatted prompt string to send to the backend.
            schema: JSON schema dict constraining the output structure.
            max_tokens: Maximum number of tokens to generate.
            top_p: Nucleus sampling probability mass. None means backend default.
            stop_sequences: Token sequences that halt generation. None means backend default.
            system: Optional system prompt injected via the backend's system channel.

        Returns:
            Parsed dict conforming to the provided schema.

        Raises:
            LLMTimeoutError: If the request exceeds the configured timeout.
            LLMRequestError: If the backend returns an error or invalid/non-dict JSON.

        Note:
            Callers (e.g. DialogueLLMClient) perform one repair retry when
            ValidationError is raised. A WARNING is logged per failed attempt;
            an ERROR is logged when the canned fallback is ultimately served.
        """


@runtime_checkable
class LLMStreamProtocol(LLMGenerateProtocol, Protocol):
    """Adds token streaming for low-latency UX (e.g. dialogue)."""

    def stream(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[str]:
        """Yield streamed tokens for low-latency UX.

        Args:
            prompt: Formatted prompt string to send to the backend.
            max_tokens: Maximum number of tokens to generate.
            temperature: Sampling temperature (0.0 = deterministic).
            top_p: Nucleus sampling probability mass. None means backend default.
            stop_sequences: Token sequences that halt generation. None means backend default.
            system: Optional system prompt injected via the backend's system channel.

        Returns:
            Async iterator yielding token strings as they arrive.

        Raises:
            LLMTimeoutError: If the stream connection exceeds the configured timeout.
            LLMRequestError: If the backend returns a stream error.
        """


@runtime_checkable
class LLMClientProtocol(LLMStructuredProtocol, LLMStreamProtocol, Protocol):
    """Full LLM adapter contract: generate + structured + stream + health + name.

    Composes every sub-protocol. Concrete adapters (ollama, mock) implement this;
    consumers should depend on the narrowest sub-protocol they actually use.
    """
