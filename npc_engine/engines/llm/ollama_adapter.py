"""
ollama_adapter.py - HTTP adapter for Ollama-compatible backend.

Does NOT: choose backend implementations.

Dependencies injected: base_url, model_name, timeout_seconds.
"""

from typing import Any, AsyncIterator
import json

import httpx

from engines.llm.protocols import LLMClientProtocol
from utils.errors import LLMRequestError, LLMTimeoutError


class OllamaAdapter(LLMClientProtocol):
    """Adapter for Ollama generation endpoints."""

    def __init__(self, base_url: str, model_name: str, timeout_seconds: float):
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds

    async def generate(self, prompt: str, max_tokens: int, temperature: float) -> str:
        payload = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(f"{self._base_url}/api/generate", json=payload)
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
        if "error" in data:
            raise LLMRequestError(model=self.model_name(), detail=f"backend_error:{data['error']}")
        return str(data.get("response", ""))

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
    ) -> dict[str, Any]:
        payload = {
            "model": self._model_name,
            "prompt": f"{prompt}\n\nRequired JSON schema:\n{json.dumps(schema, ensure_ascii=True)}",
            "stream": False,
            "format": "json",
            "options": {
                "num_predict": max_tokens,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(f"{self._base_url}/api/generate", json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise LLMTimeoutError(model=self.model_name(), timeout_s=self._timeout_seconds) from error
        except httpx.HTTPError as error:
            raise LLMRequestError(model=self.model_name(), detail="http_error") from error
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise LLMRequestError(model=self.model_name(), detail="invalid_json_shape")
            if "error" in data:
                raise LLMRequestError(model=self.model_name(), detail=f"backend_error:{data['error']}")
            parsed = json.loads(str(data.get("response", "")))
        except ValueError as error:
            raise LLMRequestError(model=self.model_name(), detail="invalid_json") from error
        if not isinstance(parsed, dict):
            raise LLMRequestError(model=self.model_name(), detail="invalid_json_shape")
        return dict(parsed)

    async def stream(self, prompt: str, max_tokens: int, temperature: float) -> AsyncIterator[str]:
        payload = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": True,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                async with client.stream("POST", f"{self._base_url}/api/generate", json=payload) as response:
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
                        token = str(chunk.get("response", ""))
                        if token != "":
                            yield token
                    return
        except httpx.TimeoutException as error:
            raise LLMTimeoutError(model=self.model_name(), timeout_s=self._timeout_seconds) from error
        except httpx.HTTPError as error:
            raise LLMRequestError(model=self.model_name(), detail="stream_http_error") from error

    def model_name(self) -> str:
        return self._model_name
