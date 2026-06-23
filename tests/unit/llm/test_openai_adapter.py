"""
test_openai_adapter.py - Unit tests for the OpenAI-compatible LLM adapter (SHIP-02 / DEC-126).

Does NOT: call live LLM services (HTTP client is monkeypatched).

Dependencies injected: Monkeypatched httpx.AsyncClient.
"""

import pytest

from npc_engine.engines.llm.openai_adapter import OpenAICompatibleAdapter
from npc_engine.utils.errors import LLMRequestError


class _FakeResponse:
    """Minimal fake HTTP response."""

    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def _make_capturing_client(payload):
    """Return a fake AsyncClient class capturing the last posted body."""

    class _Client:
        last_payload: dict = {}

        def __init__(self, *args, **kwargs):
            type(self).init_kwargs = kwargs

        async def post(self, url: str, json: dict):
            type(self).last_payload = json
            return _FakeResponse(payload=payload)

        async def get(self, url: str, timeout: float | None = None):
            return _FakeResponse(payload={"data": []})

        async def aclose(self) -> None:
            return None

    return _Client


def _adapter() -> OpenAICompatibleAdapter:
    return OpenAICompatibleAdapter(
        base_url="https://api.example.com/v1",
        api_key="sk-test",
        model_name="gpt-4o-mini",
        timeout_seconds=1.0,
    )


@pytest.mark.asyncio
async def test_generate_returns_message_content(monkeypatch) -> None:
    payload = {"choices": [{"message": {"content": "hello world"}}]}
    monkeypatch.setattr(
        "npc_engine.engines.llm.openai_adapter.httpx.AsyncClient",
        _make_capturing_client(payload),
    )
    result = await _adapter().generate(prompt="p", max_tokens=10, temperature=0.2)
    assert result == "hello world"


@pytest.mark.asyncio
async def test_generate_forwards_system_top_p_and_stop(monkeypatch) -> None:
    payload = {"choices": [{"message": {"content": "ok"}}]}
    client_cls = _make_capturing_client(payload)
    monkeypatch.setattr("npc_engine.engines.llm.openai_adapter.httpx.AsyncClient", client_cls)
    await _adapter().generate(
        prompt="p", max_tokens=10, temperature=0.2, top_p=0.8,
        stop_sequences=["STOP"], system="be terse",
    )
    body = client_cls.last_payload
    assert body["messages"][0] == {"role": "system", "content": "be terse"}
    assert body["messages"][-1] == {"role": "user", "content": "p"}
    assert body["top_p"] == 0.8
    assert body["stop"] == ["STOP"]


@pytest.mark.asyncio
async def test_generate_omits_optional_fields_when_none(monkeypatch) -> None:
    payload = {"choices": [{"message": {"content": "ok"}}]}
    client_cls = _make_capturing_client(payload)
    monkeypatch.setattr("npc_engine.engines.llm.openai_adapter.httpx.AsyncClient", client_cls)
    await _adapter().generate(prompt="p", max_tokens=10, temperature=0.2)
    body = client_cls.last_payload
    assert "top_p" not in body
    assert "stop" not in body
    assert all(m["role"] != "system" for m in body["messages"])


@pytest.mark.asyncio
async def test_generate_raises_on_backend_error_payload(monkeypatch) -> None:
    payload = {"error": {"message": "invalid key"}}
    monkeypatch.setattr(
        "npc_engine.engines.llm.openai_adapter.httpx.AsyncClient",
        _make_capturing_client(payload),
    )
    with pytest.raises(LLMRequestError):
        await _adapter().generate(prompt="p", max_tokens=10, temperature=0.2)


@pytest.mark.asyncio
async def test_generate_raises_on_non_dict_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        "npc_engine.engines.llm.openai_adapter.httpx.AsyncClient",
        _make_capturing_client(["unexpected"]),
    )
    with pytest.raises(LLMRequestError):
        await _adapter().generate(prompt="p", max_tokens=10, temperature=0.2)


@pytest.mark.asyncio
async def test_generate_structured_parses_json_content(monkeypatch) -> None:
    payload = {"choices": [{"message": {"content": '{"ok": true}'}}]}
    client_cls = _make_capturing_client(payload)
    monkeypatch.setattr("npc_engine.engines.llm.openai_adapter.httpx.AsyncClient", client_cls)
    result = await _adapter().generate_structured(prompt="p", schema={}, max_tokens=10)
    assert result == {"ok": True}
    assert client_cls.last_payload["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_generate_structured_rejects_invalid_json(monkeypatch) -> None:
    payload = {"choices": [{"message": {"content": "not-json"}}]}
    monkeypatch.setattr(
        "npc_engine.engines.llm.openai_adapter.httpx.AsyncClient",
        _make_capturing_client(payload),
    )
    with pytest.raises(LLMRequestError):
        await _adapter().generate_structured(prompt="p", schema={}, max_tokens=10)


class _FakeStreamResponse:
    """SSE stream with content deltas, a noise line, and a terminator."""

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for line in [
            'data: {"choices": [{"delta": {"content": "hel"}}]}',
            "",
            'data: {"choices": [{"delta": {"content": "lo"}}]}',
            "data: [DONE]",
        ]:
            yield line

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeStreamingClient:
    def __init__(self, *args, **kwargs):
        pass

    def stream(self, method: str, url: str, json: dict):
        return _FakeStreamResponse()

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_stream_yields_delta_content_and_stops_on_done(monkeypatch) -> None:
    monkeypatch.setattr(
        "npc_engine.engines.llm.openai_adapter.httpx.AsyncClient",
        _FakeStreamingClient,
    )
    chunks = []
    async for token in _adapter().stream(prompt="p", max_tokens=10, temperature=0.2):
        chunks.append(token)
    assert chunks == ["hel", "lo"]


@pytest.mark.asyncio
async def test_health_check_true_on_models_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "npc_engine.engines.llm.openai_adapter.httpx.AsyncClient",
        _make_capturing_client({"data": []}),
    )
    assert await _adapter().health_check() is True


def test_model_name_returns_configured_model() -> None:
    assert _adapter().model_name() == "gpt-4o-mini"
