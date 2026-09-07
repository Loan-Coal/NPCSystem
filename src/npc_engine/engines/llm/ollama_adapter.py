"""
ollama_adapter.py - HTTP adapter for Ollama-compatible backend.
Layer: engines
Purpose: HTTP adapter for Ollama-compatible backend.

Does NOT: choose backend implementations, or shape the request body (see ollama_payload).

Dependencies injected: base_url, model_name, timeout_seconds, keep_alive.
"""
from __future__ import annotations

from time import perf_counter
from typing import Any, AsyncIterator
import json

import httpx

from npc_engine.config import DEFAULT_OLLAMA_KEEP_ALIVE, get_settings
from npc_engine.engines.llm.llm_metrics import (
    OLLAMA_BACKEND_LABEL,
    LlmCallMode,
    record_llm_backend_metrics,
)
from npc_engine.engines.llm.ollama_payload import build_ollama_options, build_ollama_payload
from npc_engine.engines.llm.protocols import LLMClientProtocol
from npc_engine.engines.llm.prompt_eval_log import log_prompt_eval
from npc_engine.utils.errors import LLMRequestError, LLMTimeoutError


class OllamaAdapter(LLMClientProtocol):
    """Adapter for Ollama generation endpoints."""

    def __init__(
        self,
        base_url: str,
        model_name: str,
        timeout_seconds: float,
        keep_alive: str = DEFAULT_OLLAMA_KEEP_ALIVE,
        engine_name: str = "unknown",
    ) -> None:
        """Initialise the adapter with Ollama endpoint configuration.

        Args:
            base_url: Root URL of the Ollama server (trailing slash stripped).
            model_name: Ollama model tag to use in all requests.
            timeout_seconds: Per-request timeout in seconds.
            keep_alive: How long Ollama keeps the model resident after a request.
                Ollama's own default is 5m, which evicts the model between play
                sessions and costs a measured 10.3s reload on the next turn.
            engine_name: Engine this adapter was built for, used only as a metric
                label. Every engine shares one backend and one model, so without it
                all five collapse into a single unattributable bucket.
        """
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._keep_alive = keep_alive
        self._engine_name = engine_name
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    def _record_reply(
        self, *, reply: dict[str, Any], payload: dict[str, Any], started_at: float, mode: LlmCallMode
    ) -> None:
        """Emit the log record and the metrics for one completed backend call."""
        log_prompt_eval(reply=reply, payload=payload, started_at=started_at)
        record_llm_backend_metrics(
            backend=OLLAMA_BACKEND_LABEL,
            engine=self._engine_name,
            model=self.model_name(),
            mode=mode,
            started_at=started_at,
            load_duration_ns=reply.get("load_duration"),
        )

    async def close(self) -> None:
        """Release the shared HTTP client. Call at application shutdown."""
        await self._client.aclose()

    async def health_check(self) -> bool:
        """Return True if the Ollama backend is reachable. Non-raising.

        Returns:
            True if the /api/tags endpoint responds with HTTP 200, False otherwise.
        """
        try:
            response = await self._client.get(f"{self._base_url}/api/tags", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    async def generate(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
        seed: int | None = None,
    ) -> str:
        """Send a plain-text generation request to the Ollama backend.

        Args:
            prompt: Formatted prompt string.
            max_tokens: Maximum tokens to generate (mapped to num_predict).
            temperature: Sampling temperature.
            top_p: Nucleus sampling probability mass. None means backend default.
            stop_sequences: Token sequences that halt generation (mapped to stop). None means backend default.
            seed: Deterministic sampling seed (mapped to options.seed). None means backend default.

        Returns:
            Generated text from the backend "response" field.

        Raises:
            LLMTimeoutError: If the HTTP request times out.
            LLMRequestError: If the backend returns an HTTP error, invalid JSON, or a backend error field.
        """
        options = build_ollama_options(
            max_tokens=max_tokens,
            temperature=temperature,
            num_ctx=get_settings().OLLAMA_CONTEXT_LENGTH,
            top_p=top_p,
            stop_sequences=stop_sequences,
            seed=seed,
        )
        payload = build_ollama_payload(
            model=self._model_name,
            prompt=prompt,
            options=options,
            keep_alive=self._keep_alive,
            system=system,
        )
        started_at = perf_counter()
        try:
            response = await self._client.post(f"{self._base_url}/api/generate", json=payload)
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
        if "error" in data:
            raise LLMRequestError(model=self.model_name(), detail=f"backend_error:{data['error']}")
        self._record_reply(reply=data, payload=payload, started_at=started_at, mode="generate")
        return str(data.get("response", ""))

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Send a schema-constrained JSON generation request to the Ollama backend.

        Args:
            prompt: Formatted prompt string.
            schema: JSON schema dict passed as Ollama's ``format`` field to constrain output shape.
            max_tokens: Maximum tokens to generate (mapped to num_predict).
            top_p: Nucleus sampling probability mass. None means backend default.
            stop_sequences: Token sequences that halt generation (mapped to stop). None means backend default.
            seed: Deterministic sampling seed (mapped to options.seed). None means backend default.

        Returns:
            Parsed dict from the "response" field of the Ollama reply.

        Raises:
            LLMTimeoutError: If the HTTP request times out.
            LLMRequestError: If the backend returns an HTTP error, backend error field, or non-dict JSON.
        """
        settings = get_settings()
        options = build_ollama_options(
            max_tokens=max_tokens,
            temperature=settings.STRUCTURED_OUTPUT_TEMPERATURE,
            num_ctx=settings.OLLAMA_CONTEXT_LENGTH,
            top_p=top_p,
            stop_sequences=stop_sequences,
            seed=seed,
        )
        payload = build_ollama_payload(
            model=self._model_name,
            prompt=prompt,
            options=options,
            keep_alive=self._keep_alive,
            schema=schema,
            system=system,
        )
        started_at = perf_counter()
        try:
            response = await self._client.post(f"{self._base_url}/api/generate", json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as error:
            raise LLMTimeoutError(model=self.model_name(), timeout_s=self._timeout_seconds) from error
        except httpx.HTTPStatusError as error:
            raise LLMRequestError(model=self.model_name(), detail=f"http_error:{error.response.status_code}") from error
        except httpx.HTTPError as error:
            raise LLMRequestError(model=self.model_name(), detail="http_error") from error
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise LLMRequestError(model=self.model_name(), detail="invalid_json_shape")
            if "error" in data:
                raise LLMRequestError(model=self.model_name(), detail=f"backend_error:{data['error']}")
            self._record_reply(reply=data, payload=payload, started_at=started_at, mode="structured")
            parsed = json.loads(str(data.get("response", "")))
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
        seed: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream tokens from the Ollama backend line by line.

        Args:
            prompt: Formatted prompt string.
            max_tokens: Maximum tokens to generate (mapped to num_predict).
            temperature: Sampling temperature.
            top_p: Nucleus sampling probability mass. None means backend default.
            stop_sequences: Token sequences that halt generation (mapped to stop). None means backend default.
            seed: Deterministic sampling seed (mapped to options.seed). None means backend default.

        Returns:
            Async iterator yielding non-empty token strings from each streamed JSON line.

        Raises:
            LLMTimeoutError: If the stream connection times out.
            LLMRequestError: If the backend returns an HTTP stream error or a backend error field.
        """
        options = build_ollama_options(
            max_tokens=max_tokens,
            temperature=temperature,
            num_ctx=get_settings().OLLAMA_CONTEXT_LENGTH,
            top_p=top_p,
            stop_sequences=stop_sequences,
            seed=seed,
        )
        payload = build_ollama_payload(
            model=self._model_name,
            prompt=prompt,
            options=options,
            keep_alive=self._keep_alive,
            stream=True,
            system=system,
        )
        started_at = perf_counter()
        try:
            async with self._client.stream("POST", f"{self._base_url}/api/generate", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip() == "":
                        continue
                    try:
                        chunk = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(chunk, dict):
                        continue
                    if "error" in chunk:
                        raise LLMRequestError(model=self.model_name(), detail=f"stream_backend_error:{chunk['error']}")
                    if chunk.get("done") is True:
                        self._record_reply(
                            reply=chunk, payload=payload, started_at=started_at, mode="stream"
                        )
                    token = str(chunk.get("response", ""))
                    if token != "":
                        yield token
                return
        except httpx.TimeoutException as error:
            raise LLMTimeoutError(model=self.model_name(), timeout_s=self._timeout_seconds) from error
        except httpx.HTTPError as error:
            raise LLMRequestError(model=self.model_name(), detail="stream_http_error") from error

    def model_name(self) -> str:
        """Return the configured Ollama model tag.

        Returns:
            Model name string as provided at construction time.
        """
        return self._model_name
