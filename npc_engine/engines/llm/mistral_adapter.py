"""
mistral_adapter.py - HTTP adapter for Mistral-compatible backend.

Does NOT: choose backend implementations.

Dependencies injected: base_url, timeout_seconds.
"""

from typing import Any, AsyncIterator

import httpx

from engines.llm.protocols import LLMClientProtocol
from utils.errors import LLMRequestError, LLMTimeoutError


class MistralAdapter(LLMClientProtocol):
    """Adapter for Mistral completion endpoints."""

    def __init__(self, base_url: str, timeout_seconds: float):
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds

    async def generate(self, prompt: str, max_tokens: int, temperature: float) -> str:
        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(f"{self._base_url}/generate", json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise LLMTimeoutError(model=self.model_name(), timeout_s=self._timeout_seconds) from error
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
    ) -> dict[str, Any]:
        payload = {
            "prompt": prompt,
            "schema": schema,
            "max_tokens": max_tokens,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(f"{self._base_url}/generate_structured", json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise LLMTimeoutError(model=self.model_name(), timeout_s=self._timeout_seconds) from error
        except httpx.HTTPError as error:
            raise LLMRequestError(model=self.model_name(), detail="http_error") from error
        try:
            data = response.json()
        except ValueError as error:
            raise LLMRequestError(model=self.model_name(), detail="invalid_json") from error
        if not isinstance(data, dict):
            raise LLMRequestError(model=self.model_name(), detail="invalid_json_shape")
        return dict(data)

    async def stream(self, prompt: str, max_tokens: int, temperature: float) -> AsyncIterator[str]:
        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                async with client.stream("POST", f"{self._base_url}/stream", json=payload) as response:
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
        return "mistral7b"
