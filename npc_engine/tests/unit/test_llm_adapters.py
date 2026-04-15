"""
test_llm_adapters.py - Unit tests for LLM adapter error normalization.

Does NOT: call live LLM services.

Dependencies injected: Monkeypatched HTTP client.
"""

import pytest

from engines.llm.mistral_adapter import MistralAdapter
from engines.llm.ollama_adapter import OllamaAdapter
from utils.errors import LLMRequestError


class _FakeResponse:
    """Minimal fake HTTP response."""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _FakeClient:
    """Minimal fake async client for adapter tests."""

    def __init__(self, timeout: float):
        self._timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, json: dict):
        return _FakeResponse(payload=["not", "a", "dict"])


class _FakeOllamaClient:
    """Minimal fake async client for Ollama adapter tests."""

    def __init__(self, timeout: float):
        self._timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, json: dict):
        return _FakeResponse(payload={"response": "not-json"})


class _FakeOllamaClientNonDict:
    """Returns a non-dict payload for Ollama generate tests."""

    def __init__(self, timeout: float):
        self._timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, json: dict):
        return _FakeResponse(payload=["unexpected"])


class _FakeStreamResponse:
    """Minimal streaming response with mixed valid and invalid lines."""

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for line in ["{\"response\": \"hello\"}", "not-json", "[]", "{\"response\": \" world\"}"]:
            yield line

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeOllamaStreamingClient:
    """Minimal async client for stream tests."""

    def __init__(self, timeout: float):
        self._timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, method: str, url: str, json: dict):
        return _FakeStreamResponse()


class _FakeOllamaClientBackendError:
    """Returns an Ollama error payload to validate adapter normalization."""

    def __init__(self, timeout: float):
        self._timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, json: dict):
        return _FakeResponse(payload={"error": "model not found"})


class _FakeStreamErrorResponse:
    """Streaming response that includes a backend error chunk."""

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for line in ["{\"response\": \"hello\"}", "{\"error\": \"backend unavailable\"}"]:
            yield line

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeOllamaStreamingClientWithError:
    """Minimal async client for stream error tests."""

    def __init__(self, timeout: float):
        self._timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def stream(self, method: str, url: str, json: dict):
        return _FakeStreamErrorResponse()


@pytest.mark.asyncio
async def test_generate_structured_rejects_non_dict_json(monkeypatch) -> None:
    monkeypatch.setattr("engines.llm.mistral_adapter.httpx.AsyncClient", _FakeClient)
    adapter = MistralAdapter(base_url="http://fake", timeout_seconds=1.0)

    with pytest.raises(LLMRequestError):
        await adapter.generate_structured(prompt="p", schema={}, max_tokens=10)


@pytest.mark.asyncio
async def test_ollama_generate_structured_rejects_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr("engines.llm.ollama_adapter.httpx.AsyncClient", _FakeOllamaClient)
    adapter = OllamaAdapter(base_url="http://fake", model_name="mixtral:8x7b", timeout_seconds=1.0)

    with pytest.raises(LLMRequestError):
        await adapter.generate_structured(prompt="p", schema={}, max_tokens=10)


@pytest.mark.asyncio
async def test_ollama_generate_rejects_non_dict_json_payload(monkeypatch) -> None:
    monkeypatch.setattr("engines.llm.ollama_adapter.httpx.AsyncClient", _FakeOllamaClientNonDict)
    adapter = OllamaAdapter(base_url="http://fake", model_name="mixtral:8x7b", timeout_seconds=1.0)

    with pytest.raises(LLMRequestError):
        await adapter.generate(prompt="p", max_tokens=10, temperature=0.1)


@pytest.mark.asyncio
async def test_ollama_stream_skips_invalid_lines_and_yields_tokens(monkeypatch) -> None:
    monkeypatch.setattr("engines.llm.ollama_adapter.httpx.AsyncClient", _FakeOllamaStreamingClient)
    adapter = OllamaAdapter(base_url="http://fake", model_name="mixtral:8x7b", timeout_seconds=1.0)

    chunks = []
    async for token in adapter.stream(prompt="p", max_tokens=10, temperature=0.1):
        chunks.append(token)

    assert chunks == ["hello", " world"]


@pytest.mark.asyncio
async def test_ollama_generate_rejects_backend_error_payload(monkeypatch) -> None:
    monkeypatch.setattr("engines.llm.ollama_adapter.httpx.AsyncClient", _FakeOllamaClientBackendError)
    adapter = OllamaAdapter(base_url="http://fake", model_name="mixtral:8x7b", timeout_seconds=1.0)

    with pytest.raises(LLMRequestError):
        await adapter.generate(prompt="p", max_tokens=10, temperature=0.1)


@pytest.mark.asyncio
async def test_ollama_stream_raises_on_backend_error_chunk(monkeypatch) -> None:
    monkeypatch.setattr("engines.llm.ollama_adapter.httpx.AsyncClient", _FakeOllamaStreamingClientWithError)
    adapter = OllamaAdapter(base_url="http://fake", model_name="mixtral:8x7b", timeout_seconds=1.0)

    with pytest.raises(LLMRequestError):
        async for _ in adapter.stream(prompt="p", max_tokens=10, temperature=0.1):
            pass
