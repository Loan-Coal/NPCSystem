"""
mistral_adapter.py - HTTP adapter for Mistral-compatible backend.

Does NOT: choose backend implementations.

Dependencies injected: base_url, model_name, timeout_seconds.
"""

from typing import Any, AsyncIterator

import httpx

from npc_engine.engines.llm.protocols import LLMClientProtocol
from npc_engine.utils.errors import LLMRequestError, LLMTimeoutError


class MistralAdapter(LLMClientProtocol):
    """Adapter for Mistral completion endpoints."""

    def __init__(self, base_url: str, model_name: str, timeout_seconds: float) -> None:
        """Initialise the adapter with endpoint configuration.

        Args:
            base_url: Root URL of the Mistral-compatible HTTP backend.
            model_name: Model tag to use; returned by model_name() and used in metrics.
            timeout_seconds: Per-request timeout in seconds.
        """
        self._base_url = base_url
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def close(self) -> None:
        """Release the shared HTTP client. Call at application shutdown."""
        await self._client.aclose()

    async def health_check(self) -> bool:
        """Return True — Mistral is an external service checked at startup. Non-raising.

        Returns:
            Always True; Mistral availability is validated via configuration.
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
        """Send a plain-text generation request to the Mistral backend.

        Args:
            prompt: Formatted prompt string.
            max_tokens: Maximum tokens the backend should generate.
            temperature: Sampling temperature.
            top_p: Nucleus sampling probability mass. None means backend default.
            stop_sequences: Token sequences that halt generation. None means backend default.
            system: Optional system prompt prepended to the user prompt.

        Returns:
            Generated text from the backend "text" field.

        Raises:
            LLMTimeoutError: If the HTTP request times out.
            LLMRequestError: If the backend returns an HTTP error or invalid JSON.
        """
        effective_prompt = f"{system}\n\n{prompt}" if system is not None else prompt
        payload: dict = {"prompt": effective_prompt, "max_tokens": max_tokens, "temperature": temperature}
        if top_p is not None:
            payload["top_p"] = top_p
        if stop_sequences is not None:
            payload["stop_sequences"] = stop_sequences
        try:
            response = await self._client.post(f"{self._base_url}/generate", json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise LLMTimeoutError(model=self.model_name(), timeout_s=self._timeout_seconds) from error
        except httpx.HTTPStatusError as error:
            raise LLMRequestError(model=self.model_name(), detail=f"http_error:{error.response.status_code}") from error
        except httpx.HTTPError as error:
            raise LLMRequestError(model=self.model_name(), detail="http_error") from error
        try:
            data = response.json()
        except ValueError as error:
            raise LLMRequestError(model=self.model_name(), detail="invalid_json") from error
        return str(data.get("text", ""))

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Send a schema-constrained JSON generation request to the Mistral backend.

        Args:
            prompt: Formatted prompt string.
            schema: JSON schema dict constraining the output.
            max_tokens: Maximum tokens the backend should generate.
            top_p: Nucleus sampling probability mass. None means backend default.
            stop_sequences: Token sequences that halt generation. None means backend default.
            system: Optional system prompt prepended to the user prompt.

        Returns:
            Parsed dict from the backend response.

        Raises:
            LLMTimeoutError: If the HTTP request times out.
            LLMRequestError: If the backend returns an HTTP error, invalid JSON, or a non-dict body.
        """
        effective_prompt = f"{system}\n\n{prompt}" if system is not None else prompt
        payload: dict = {"prompt": effective_prompt, "schema": schema, "max_tokens": max_tokens}
        if top_p is not None:
            payload["top_p"] = top_p
        if stop_sequences is not None:
            payload["stop_sequences"] = stop_sequences
        try:
            response = await self._client.post(f"{self._base_url}/generate_structured", json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise LLMTimeoutError(model=self.model_name(), timeout_s=self._timeout_seconds) from error
        except httpx.HTTPStatusError as error:
            raise LLMRequestError(model=self.model_name(), detail=f"http_error:{error.response.status_code}") from error
        except httpx.HTTPError as error:
            raise LLMRequestError(model=self.model_name(), detail="http_error") from error
        try:
            data = response.json()
        except ValueError as error:
            raise LLMRequestError(model=self.model_name(), detail="invalid_json") from error
        if not isinstance(data, dict):
            raise LLMRequestError(model=self.model_name(), detail="invalid_json_shape")
        return dict(data)

    async def stream(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream tokens from the Mistral backend as they are generated.

        Args:
            prompt: Formatted prompt string.
            max_tokens: Maximum tokens the backend should generate.
            temperature: Sampling temperature.
            top_p: Nucleus sampling probability mass. None means backend default.
            stop_sequences: Token sequences that halt generation. None means backend default.
            system: Optional system prompt prepended to the user prompt.

        Returns:
            Async iterator yielding raw text chunks from the backend stream.

        Raises:
            LLMTimeoutError: If the stream connection times out.
            LLMRequestError: If the backend returns an HTTP stream error.
        """
        effective_prompt = f"{system}\n\n{prompt}" if system is not None else prompt
        payload: dict = {"prompt": effective_prompt, "max_tokens": max_tokens, "temperature": temperature}
        if top_p is not None:
            payload["top_p"] = top_p
        if stop_sequences is not None:
            payload["stop_sequences"] = stop_sequences
        try:
            async with self._client.stream("POST", f"{self._base_url}/stream", json=payload) as response:
                response.raise_for_status()
                async for chunk in response.aiter_text():
                    if chunk != "":
                        yield chunk
                return
        except httpx.TimeoutException as error:
            raise LLMTimeoutError(model=self.model_name(), timeout_s=self._timeout_seconds) from error
        except httpx.HTTPError as error:
            raise LLMRequestError(model=self.model_name(), detail="stream_http_error") from error

    def model_name(self) -> str:
        """Return the configured model tag.

        Returns:
            Model name string as provided at construction time.
        """
        return self._model_name
