"""
test_llm_backend_metrics.py - Every LLM call must be countable and timeable in process.

Why this exists: no LLM latency instrumentation existed anywhere in src/. Ollama returns
total_duration, load_duration, prompt_eval_duration and eval_duration on every reply and the
adapter read only the token counts, so the 3-7s dialogue budget could not be checked against
anything. load_duration gets its own metric because it is the number that moves most: a cold
load was measured at 10.3s against a 3.49-4.18s warm turn, and it is the only in-process
signal that an eviction happened despite keep_alive.

Does NOT: call a live Ollama backend, or assert on log records.

Dependencies injected: monkeypatched httpx client returning a canned Ollama reply.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.engines.llm.ollama_adapter import OllamaAdapter
from npc_engine.utils.metrics import (
    get_counter_value,
    get_metrics_registry,
    reset_metrics_registry,
)

_LOAD_NS = 10_300_000_000
# Labels are serialised sorted, and label VALUES are sanitised: "qwen2.5:7b" -> "qwen2_5_7b".
_GENERATE_KEY_SUFFIX = "|backend=ollama,engine=dialogue,mode=generate,model=qwen2_5_7b"
_LABELS = {"backend": "ollama", "engine": "dialogue", "model": "qwen2.5:7b", "mode": "generate"}


def setup_function() -> None:
    reset_metrics_registry()


class _Response:
    """Canned non-streaming Ollama reply."""

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        body: dict[str, Any] = {"response": '{"ok": true}'}
        body.update(_reply_extras)
        return body


class _StreamResponse:
    """Canned streamed Ollama reply whose terminal chunk carries the accounting."""

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        yield '{"response": "tok", "done": true}'

    async def __aenter__(self) -> "_StreamResponse":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class _Client:
    """Minimal httpx.AsyncClient stand-in."""

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout

    async def post(self, url: str, json: dict[str, Any]) -> _Response:
        return _Response()

    def stream(self, method: str, url: str, json: dict[str, Any]) -> _StreamResponse:
        return _StreamResponse()


_reply_extras: dict[str, Any] = {}


def _adapter(monkeypatch: pytest.MonkeyPatch, **extras: Any) -> OllamaAdapter:
    """Build an adapter whose backend reply carries the given extra fields."""
    global _reply_extras
    _reply_extras = dict(extras)
    monkeypatch.setattr("npc_engine.engines.llm.ollama_adapter.httpx.AsyncClient", _Client)
    return OllamaAdapter(
        base_url="http://fake",
        model_name="qwen2.5:7b",
        timeout_seconds=1.0,
        engine_name="dialogue",
    )


def _observations() -> dict[str, Any]:
    return get_metrics_registry().snapshot()["observations"]


@pytest.mark.asyncio
async def test_generate_increments_the_backend_call_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One counted call per generation, attributed to the engine that made it."""
    adapter = _adapter(monkeypatch)

    await adapter.generate(prompt="p", max_tokens=64, temperature=0.5)

    assert get_counter_value("llm_backend_calls_total", labels=_LABELS) == 1.0


@pytest.mark.asyncio
async def test_generate_structured_uses_the_structured_mode_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The structured path is the one dialogue uses and must be separable from plain text."""
    adapter = _adapter(monkeypatch)

    await adapter.generate_structured(prompt="p", schema={"type": "object"}, max_tokens=64)

    structured = {**_LABELS, "mode": "structured"}
    assert get_counter_value("llm_backend_calls_total", labels=structured) == 1.0
    assert get_counter_value("llm_backend_calls_total", labels=_LABELS) == 0.0


@pytest.mark.asyncio
async def test_stream_uses_the_stream_mode_label(monkeypatch: pytest.MonkeyPatch) -> None:
    """The streaming path reports on its terminal chunk, where Ollama puts the accounting."""
    adapter = _adapter(monkeypatch)

    async for _token in adapter.stream(prompt="p", max_tokens=64, temperature=0.5):
        pass

    assert get_counter_value("llm_backend_calls_total", labels={**_LABELS, "mode": "stream"}) == 1.0


@pytest.mark.asyncio
async def test_backend_latency_is_observed_in_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    """House convention is <x>_latency_seconds; logs carry ms, metrics carry seconds."""
    adapter = _adapter(monkeypatch)

    await adapter.generate(prompt="p", max_tokens=64, temperature=0.5)

    observed = _observations()["llm_backend_latency_seconds" + _GENERATE_KEY_SUFFIX]
    assert observed["count"] == 1.0
    assert 0.0 <= observed["sum"] < 5.0


@pytest.mark.asyncio
async def test_model_load_time_is_observed_when_the_backend_reports_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A nonzero load means the model was evicted and had to be paged back in."""
    adapter = _adapter(monkeypatch, load_duration=_LOAD_NS)

    await adapter.generate(prompt="p", max_tokens=64, temperature=0.5)

    observed = _observations()["llm_backend_load_latency_seconds" + _GENERATE_KEY_SUFFIX]
    assert observed["count"] == 1.0
    assert observed["sum"] == pytest.approx(10.3)


@pytest.mark.asyncio
async def test_an_unreported_model_load_is_not_observed_as_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """observe() folds into min/sum, so faked zeros would make the eviction signal unreadable."""
    adapter = _adapter(monkeypatch)

    await adapter.generate(prompt="p", max_tokens=64, temperature=0.5)

    assert "llm_backend_load_latency_seconds" + _GENERATE_KEY_SUFFIX not in _observations()
