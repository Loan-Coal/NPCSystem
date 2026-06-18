"""
openai_adapter.py - HTTP adapter for OpenAI-compatible /chat/completions backends.
Layer: engines
Purpose: SHIP-02 / DEC-126 bring-your-own-API-key path. Talks the OpenAI chat-completions
         wire format against a configurable base_url so one adapter serves OpenAI, OpenRouter,
         Groq, Together, DeepSeek, and local OpenAI-compatible servers (LM Studio, llama.cpp).

Does NOT: choose backend implementations (the factory does) or store the API key.

Dependencies injected: base_url, api_key, model_name, timeout_seconds.

Fallback contract: on timeout raises LLMTimeoutError; on transport/parse failure raises
LLMRequestError. Callers (DialogueLLMClient) map these to canned fallback responses.
"""
from __future__ import annotations

from typing import Any, AsyncIterator
import json

import httpx

from npc_engine.config import get_settings
from npc_engine.engines.llm.protocols import LLMClientProtocol
from npc_engine.utils.errors import LLMRequestError, LLMTimeoutError

_CHAT_COMPLETIONS_PATH = "/chat/completions"
_MODELS_PATH = "/models"
_HEALTH_TIMEOUT_SECONDS = 5.0
_JSON_OBJECT_RESPONSE_FORMAT = {"type": "json_object"}
_DONE_SENTINEL = "[DONE]"
_SSE_DATA_PREFIX = "data:"


class OpenAICompatibleAdapter(LLMClientProtocol):
    """Adapter for OpenAI-compatible /chat/completions endpoints (bearer-key auth)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        timeout_seconds: float,
    ) -> None:
        """Initialise the adapter with endpoint, key, and model configuration.

        Args:
            base_url: API root including version segment (e.g. ".../v1"); trailing slash stripped.
            api_key: Bearer token sent in the Authorization header.
            model_name: Model identifier passed in every request body.
            timeout_seconds: Per-request timeout in seconds.
        """
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def close(self) -> None:
        """Release the shared HTTP client. Call at application shutdown."""
        await self._client.aclose()

    async def health_check(self) -> bool:
        """Return True if the backend lists models successfully. Non-raising.

        Returns:
            True if GET {base_url}/models responds with HTTP 200, False otherwise.
        """
        try:
            response = await self._client.get(
                f"{self._base_url}{_MODELS_PATH}", timeout=_HEALTH_TIMEOUT_SECONDS
            )
            return response.status_code == 200
        except Exception:
            return False

    def _messages(self, prompt: str, system: str | None) -> list[dict[str, str]]:
        """Build the chat messages array, prepending a system message when given."""
        messages: list[dict[str, str]] = []
        if system is not None:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _base_body(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None,
        stop_sequences: list[str] | None,
        system: str | None,
    ) -> dict[str, Any]:
        """Assemble the shared request body, omitting None-valued optional fields."""
        body: dict[str, Any] = {
            "model": self._model_name,
            "messages": self._messages(prompt, system),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if top_p is not None:
            body["top_p"] = top_p
        if stop_sequences is not None:
            body["stop"] = stop_sequences
        return body

    async def _post_json(self, body: dict[str, Any]) -> dict[str, Any]:
        """POST a chat-completions request and return the validated JSON dict.

        Raises:
            LLMTimeoutError: If the request times out.
            LLMRequestError: On HTTP error, invalid JSON, non-dict shape, or backend error field.
        """
        try:
            response = await self._client.post(
                f"{self._base_url}{_CHAT_COMPLETIONS_PATH}", json=body
            )
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise LLMTimeoutError(model=self.model_name(), timeout_s=self._timeout_seconds) from error
        except httpx.HTTPStatusError as error:
            raise LLMRequestError(
                model=self.model_name(), detail=f"http_error:{error.response.status_code}"
            ) from error
        except httpx.HTTPError as error:
            raise LLMRequestError(model=self.model_name(), detail="http_error") from error
        try:
            data = response.json()
        except ValueError as error:
            raise LLMRequestError(model=self.model_name(), detail="invalid_json") from error
        if not isinstance(data, dict):
            raise LLMRequestError(model=self.model_name(), detail="invalid_json_shape")
        if "error" in data:
            raise LLMRequestError(model=self.model_name(), detail=f"backend_error:{data['error']}")
        return data

    def _first_content(self, data: dict[str, Any]) -> str:
        """Extract choices[0].message.content from a chat-completions reply.

        Raises:
            LLMRequestError: If the choices/message structure is missing or malformed.
        """
        choices = data.get("choices")
        if not isinstance(choices, list) or len(choices) == 0:
            raise LLMRequestError(model=self.model_name(), detail="no_choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            raise LLMRequestError(model=self.model_name(), detail="invalid_choice_shape")
        return str(message.get("content", ""))

    async def generate(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
    ) -> str:
        """Send a plain-text chat-completion request.

        Returns:
            The assistant message content of the first choice.

        Raises:
            LLMTimeoutError: If the request times out.
            LLMRequestError: On HTTP error, invalid response, or backend error field.
        """
        body = self._base_body(prompt, max_tokens, temperature, top_p, stop_sequences, system)
        data = await self._post_json(body)
        return self._first_content(data)

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
    ) -> dict[str, Any]:
        """Send a JSON-mode chat-completion request and parse the content as JSON.

        Uses response_format={"type": "json_object"} (broadly supported across
        OpenAI-compatible providers); strict json_schema response_format is deferred.

        Returns:
            The parsed JSON object from the first choice's message content.

        Raises:
            LLMTimeoutError: If the request times out.
            LLMRequestError: On HTTP error, non-JSON content, or non-object JSON.
        """
        body = self._base_body(
            prompt, max_tokens, get_settings().STRUCTURED_OUTPUT_TEMPERATURE,
            top_p, stop_sequences, system,
        )
        body["response_format"] = _JSON_OBJECT_RESPONSE_FORMAT
        data = await self._post_json(body)
        content = self._first_content(data)
        try:
            parsed = json.loads(content)
        except ValueError as error:
            raise LLMRequestError(model=self.model_name(), detail="invalid_json") from error
        if not isinstance(parsed, dict):
            raise LLMRequestError(model=self.model_name(), detail="invalid_json_shape")
        return dict(parsed)

    async def stream(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream assistant token deltas via Server-Sent Events.

        Yields:
            Non-empty delta content strings until the [DONE] sentinel.

        Raises:
            LLMTimeoutError: If the stream connection times out.
            LLMRequestError: On HTTP stream error.
        """
        body = self._base_body(prompt, max_tokens, temperature, top_p, stop_sequences, system)
        body["stream"] = True
        try:
            async with self._client.stream(
                "POST", f"{self._base_url}{_CHAT_COMPLETIONS_PATH}", json=body
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    token = _parse_sse_token(line)
                    if token == _DONE_SENTINEL:
                        return
                    if token:
                        yield token
                return
        except httpx.TimeoutException as error:
            raise LLMTimeoutError(model=self.model_name(), timeout_s=self._timeout_seconds) from error
        except httpx.HTTPError as error:
            raise LLMRequestError(model=self.model_name(), detail="stream_http_error") from error

    def model_name(self) -> str:
        """Return the configured model identifier.

        Returns:
            Model name string as provided at construction time.
        """
        return self._model_name


def _parse_sse_token(line: str) -> str:
    """Parse one SSE line into a delta token, the [DONE] sentinel, or "" to skip."""
    stripped = line.strip()
    if not stripped.startswith(_SSE_DATA_PREFIX):
        return ""
    data = stripped[len(_SSE_DATA_PREFIX):].strip()
    if data == _DONE_SENTINEL:
        return _DONE_SENTINEL
    try:
        chunk = json.loads(data)
    except ValueError:
        return ""
    if not isinstance(chunk, dict):
        return ""
    choices = chunk.get("choices")
    if not isinstance(choices, list) or len(choices) == 0:
        return ""
    delta = choices[0].get("delta") if isinstance(choices[0], dict) else None
    if not isinstance(delta, dict):
        return ""
    return str(delta.get("content", "") or "")
