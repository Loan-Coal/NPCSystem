"""
test_llm_adapters.py - Unit tests for LLM adapter error normalization.

Does NOT: call live LLM services.

Dependencies injected: Monkeypatched HTTP client.
"""

import pytest

from npc_engine.engines.llm.mistral_adapter import MistralAdapter
from npc_engine.engines.llm.ollama_adapter import OllamaAdapter
from npc_engine.utils.errors import LLMRequestError


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
    monkeypatch.setattr("npc_engine.engines.llm.mistral_adapter.httpx.AsyncClient", _FakeClient)
    adapter = MistralAdapter(base_url="http://fake", model_name="mistral7b", timeout_seconds=1.0)

    with pytest.raises(LLMRequestError):
        await adapter.generate_structured(prompt="p", schema={}, max_tokens=10)


@pytest.mark.asyncio
async def test_ollama_generate_structured_rejects_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr("npc_engine.engines.llm.ollama_adapter.httpx.AsyncClient", _FakeOllamaClient)
    adapter = OllamaAdapter(base_url="http://fake", model_name="mixtral:8x7b", timeout_seconds=1.0)

    with pytest.raises(LLMRequestError):
        await adapter.generate_structured(prompt="p", schema={}, max_tokens=10)


@pytest.mark.asyncio
async def test_ollama_generate_rejects_non_dict_json_payload(monkeypatch) -> None:
    monkeypatch.setattr("npc_engine.engines.llm.ollama_adapter.httpx.AsyncClient", _FakeOllamaClientNonDict)
    adapter = OllamaAdapter(base_url="http://fake", model_name="mixtral:8x7b", timeout_seconds=1.0)

    with pytest.raises(LLMRequestError):
        await adapter.generate(prompt="p", max_tokens=10, temperature=0.1)


@pytest.mark.asyncio
async def test_ollama_stream_skips_invalid_lines_and_yields_tokens(monkeypatch) -> None:
    monkeypatch.setattr("npc_engine.engines.llm.ollama_adapter.httpx.AsyncClient", _FakeOllamaStreamingClient)
    adapter = OllamaAdapter(base_url="http://fake", model_name="mixtral:8x7b", timeout_seconds=1.0)

    chunks = []
    async for token in adapter.stream(prompt="p", max_tokens=10, temperature=0.1):
        chunks.append(token)

    assert chunks == ["hello", " world"]


@pytest.mark.asyncio
async def test_ollama_generate_rejects_backend_error_payload(monkeypatch) -> None:
    monkeypatch.setattr("npc_engine.engines.llm.ollama_adapter.httpx.AsyncClient", _FakeOllamaClientBackendError)
    adapter = OllamaAdapter(base_url="http://fake", model_name="mixtral:8x7b", timeout_seconds=1.0)

    with pytest.raises(LLMRequestError):
        await adapter.generate(prompt="p", max_tokens=10, temperature=0.1)


@pytest.mark.asyncio
async def test_ollama_stream_raises_on_backend_error_chunk(monkeypatch) -> None:
    monkeypatch.setattr("npc_engine.engines.llm.ollama_adapter.httpx.AsyncClient", _FakeOllamaStreamingClientWithError)
    adapter = OllamaAdapter(base_url="http://fake", model_name="mixtral:8x7b", timeout_seconds=1.0)

    with pytest.raises(LLMRequestError):
        async for _ in adapter.stream(prompt="p", max_tokens=10, temperature=0.1):
            pass


# ---------------------------------------------------------------------------
# top_p and stop_sequences forwarding
# ---------------------------------------------------------------------------

class _CapturingClient:
    """Records the last payload sent via post()."""

    def __init__(self, timeout: float):
        self.last_payload: dict = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, json: dict):
        self.last_payload = json
        return _FakeResponse(payload={"text": "ok"})


_capturing_instance: _CapturingClient | None = None


def _capturing_client_factory(timeout: float) -> _CapturingClient:
    global _capturing_instance
    _capturing_instance = _CapturingClient(timeout)
    return _capturing_instance


class _CapturingOllamaClient:
    """Records the last payload for Ollama generate tests."""

    def __init__(self, timeout: float):
        self.last_payload: dict = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, json: dict):
        self.last_payload = json
        return _FakeResponse(payload={"response": '{"ok": true}'})


_capturing_ollama_instance: _CapturingOllamaClient | None = None


def _capturing_ollama_factory(timeout: float) -> _CapturingOllamaClient:
    global _capturing_ollama_instance
    _capturing_ollama_instance = _CapturingOllamaClient(timeout)
    return _capturing_ollama_instance


@pytest.mark.asyncio
async def test_mistral_generate_forwards_top_p_and_stop_sequences(monkeypatch) -> None:
    from npc_engine.engines.llm.mistral_adapter import MistralAdapter

    monkeypatch.setattr("npc_engine.engines.llm.mistral_adapter.httpx.AsyncClient", _capturing_client_factory)
    adapter = MistralAdapter(base_url="http://fake", model_name="mistral7b", timeout_seconds=1.0)
    await adapter.generate(prompt="p", max_tokens=10, temperature=0.5, top_p=0.9, stop_sequences=["END"])

    assert _capturing_instance is not None
    payload = _capturing_instance.last_payload
    assert payload["top_p"] == 0.9
    assert payload["stop_sequences"] == ["END"]


@pytest.mark.asyncio
async def test_mistral_generate_omits_top_p_when_none(monkeypatch) -> None:
    from npc_engine.engines.llm.mistral_adapter import MistralAdapter

    monkeypatch.setattr("npc_engine.engines.llm.mistral_adapter.httpx.AsyncClient", _capturing_client_factory)
    adapter = MistralAdapter(base_url="http://fake", model_name="mistral7b", timeout_seconds=1.0)
    await adapter.generate(prompt="p", max_tokens=10, temperature=0.5)

    assert _capturing_instance is not None
    payload = _capturing_instance.last_payload
    assert "top_p" not in payload
    assert "stop_sequences" not in payload


@pytest.mark.asyncio
async def test_ollama_generate_structured_forwards_top_p_and_stop(monkeypatch) -> None:
    monkeypatch.setattr("npc_engine.engines.llm.ollama_adapter.httpx.AsyncClient", _capturing_ollama_factory)
    adapter = OllamaAdapter(base_url="http://fake", model_name="mixtral:8x7b", timeout_seconds=1.0)
    await adapter.generate_structured(prompt="p", schema={}, max_tokens=10, top_p=0.8, stop_sequences=["STOP"])

    assert _capturing_ollama_instance is not None
    options = _capturing_ollama_instance.last_payload["options"]
    assert options["top_p"] == 0.8
    assert options["stop"] == ["STOP"]


@pytest.mark.asyncio
async def test_ollama_generate_structured_omits_top_p_when_none(monkeypatch) -> None:
    monkeypatch.setattr("npc_engine.engines.llm.ollama_adapter.httpx.AsyncClient", _capturing_ollama_factory)
    adapter = OllamaAdapter(base_url="http://fake", model_name="mixtral:8x7b", timeout_seconds=1.0)
    await adapter.generate_structured(prompt="p", schema={}, max_tokens=10)

    assert _capturing_ollama_instance is not None
    options = _capturing_ollama_instance.last_payload["options"]
    assert "top_p" not in options
    assert "stop" not in options
