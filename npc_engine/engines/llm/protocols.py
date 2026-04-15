"""
protocols.py - Shared protocol for LLM backend adapters.

Does NOT: implement network requests.

Dependencies injected: None.
"""

from typing import Any, AsyncIterator, Protocol, runtime_checkable


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Contract for all LLM adapter implementations."""

    async def generate(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Generate plain text output."""

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
    ) -> dict[str, Any]:
        """Generate schema-constrained JSON-like output."""

    def stream(self, prompt: str, max_tokens: int, temperature: float) -> AsyncIterator[str]:
        """Yield streamed tokens for low-latency UX."""

    def model_name(self) -> str:
        """Return backend model identifier."""
