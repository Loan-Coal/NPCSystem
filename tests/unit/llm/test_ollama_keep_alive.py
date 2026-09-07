"""
test_ollama_keep_alive.py - Every Ollama request must carry the model-residency window.

Why this exists: nothing sent keep_alive, so Ollama's 5-minute default evicted the model
between play sessions and the next dialogue turn paid a measured 10.3s cold load against a
3.49-4.18s warm turn. The field is TOP-LEVEL: placed inside `options` the backend accepts
the request and silently ignores it, leaving the default timer in force with nothing in the
logs -- so each test pins the placement, not just the presence.

Does NOT: call a live Ollama backend, or assert any generation behaviour.

Dependencies injected: monkeypatched httpx client capturing the outbound payload.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.config import DEFAULT_OLLAMA_KEEP_ALIVE
from npc_engine.engines.llm.ollama_adapter import OllamaAdapter


class _Response:
    """Canned non-streaming Ollama reply."""

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"response": '{"ok": true}'}


class _StreamResponse:
    """Canned streamed Ollama reply yielding one token."""

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        yield '{"response": "tok", "done": true}'

    async def __aenter__(self) -> "_StreamResponse":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class _CapturingClient:
    """Records the last outbound payload for both the POST and stream paths."""

    def __init__(self, timeout: float) -> None:
        self.last_payload: dict[str, Any] = {}

    async def post(self, url: str, json: dict[str, Any]) -> _Response:
        self.last_payload = json
        return _Response()

    def stream(self, method: str, url: str, json: dict[str, Any]) -> _StreamResponse:
        self.last_payload = json
        return _StreamResponse()


_captured: _CapturingClient | None = None


def _factory(timeout: float) -> _CapturingClient:
    global _captured
    _captured = _CapturingClient(timeout)
    return _captured


def _adapter(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> OllamaAdapter:
    """Build an adapter over the capturing client, forwarding constructor overrides."""
    monkeypatch.setattr("npc_engine.engines.llm.ollama_adapter.httpx.AsyncClient", _factory)
    return OllamaAdapter(
        base_url="http://fake", model_name="qwen2.5:7b", timeout_seconds=1.0, **kwargs
    )


def _payload() -> dict[str, Any]:
    assert _captured is not None
    return _captured.last_payload


@pytest.mark.asyncio
async def test_generate_sends_keep_alive_as_a_top_level_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inside `options` the backend would ignore it and keep the 5-minute default."""
    adapter = _adapter(monkeypatch)

    await adapter.generate(prompt="p", max_tokens=64, temperature=0.5)

    assert _payload()["keep_alive"] == DEFAULT_OLLAMA_KEEP_ALIVE
    assert "keep_alive" not in _payload()["options"]


@pytest.mark.asyncio
async def test_generate_structured_sends_keep_alive_as_a_top_level_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The structured path is the one dialogue actually uses."""
    adapter = _adapter(monkeypatch)

    await adapter.generate_structured(prompt="p", schema={"type": "object"}, max_tokens=64)

    assert _payload()["keep_alive"] == DEFAULT_OLLAMA_KEEP_ALIVE
    assert "keep_alive" not in _payload()["options"]


@pytest.mark.asyncio
async def test_stream_sends_keep_alive_as_a_top_level_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The streaming path must not be the one that silently reverts to 5m."""
    adapter = _adapter(monkeypatch)

    async for _token in adapter.stream(prompt="p", max_tokens=64, temperature=0.5):
        pass

    assert _payload()["keep_alive"] == DEFAULT_OLLAMA_KEEP_ALIVE
    assert "keep_alive" not in _payload()["options"]


@pytest.mark.asyncio
async def test_a_constructor_keep_alive_overrides_the_shipped_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The judge client relies on this to keep its own residency behaviour."""
    adapter = _adapter(monkeypatch, keep_alive="5m")

    await adapter.generate(prompt="p", max_tokens=64, temperature=0.5)

    assert _payload()["keep_alive"] == "5m"
