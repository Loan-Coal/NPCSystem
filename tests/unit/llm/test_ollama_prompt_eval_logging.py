"""
test_ollama_prompt_eval_logging.py - The adapter must report what the backend actually
tokenised (P0 of the prompt-window plan).

Why this exists: `num_ctx` is sent on every request, and the assembled system prompt alone
is larger than the shipped 4096 window, so Ollama has been truncating every prompt. Nothing
recorded `prompt_eval_count`, so that was unobservable -- the engine could not tell the
difference between "the context reached the model" and "the context was cut off before the
model saw it". These tests pin the evidence channel, not a behaviour change.

Does NOT: call a live Ollama backend, or assert any generation behaviour.

Dependencies injected: monkeypatched httpx client returning a canned Ollama reply.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from npc_engine.config import get_settings
from npc_engine.engines.llm.ollama_adapter import OllamaAdapter
from npc_engine.engines.llm.prompt_eval_log import PROMPT_EVAL_LOG_EVENT

_PROMPT_EVAL_LOGGER = "npc_engine.engines.llm.prompt_eval_log"

_PROMPT_EVAL_COUNT = 3584
_EVAL_COUNT = 40
_SYSTEM_TEXT = "s" * 400
_PROMPT_TEXT = "p" * 200


class _Response:
    """Canned non-streaming Ollama reply."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _Client:
    """Minimal httpx.AsyncClient stand-in returning a fixed reply."""

    def __init__(self, timeout: float) -> None:
        self.payload: dict[str, Any] = {}

    async def post(self, url: str, json: dict[str, Any]) -> _Response:
        self.payload = json
        body: dict[str, Any] = {"response": '{"ok": true}'}
        body.update(_reply_extras)
        return _Response(body)


_reply_extras: dict[str, Any] = {}


def _adapter(monkeypatch: pytest.MonkeyPatch, **extras: Any) -> OllamaAdapter:
    """Build an adapter whose backend reply carries the given extra fields."""
    global _reply_extras
    _reply_extras = dict(extras)
    monkeypatch.setattr(
        "npc_engine.engines.llm.ollama_adapter.httpx.AsyncClient",
        _Client,
    )
    return OllamaAdapter(base_url="http://fake", model_name="qwen2.5:7b", timeout_seconds=1.0)


class _RecordCollector(logging.Handler):
    """Collects records straight off the module logger."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture(name="prompt_eval_records")
def _prompt_eval_records_fixture():
    """Capture prompt-eval records without depending on global logging config.

    caplog attaches to the ROOT logger, but utils.logging.configure_logging sets
    propagate=False on the `npc_engine` logger. Any earlier test that configures
    logging would therefore make these assertions silently unobservable -- the exact
    class of false-green this whole phase exists to remove. Attaching to the module
    logger directly makes the test independent of suite ordering.
    """
    logger = logging.getLogger(_PROMPT_EVAL_LOGGER)
    collector = _RecordCollector()
    previous_level = logger.level
    logger.addHandler(collector)
    logger.setLevel(logging.INFO)
    try:
        yield collector.records
    finally:
        logger.removeHandler(collector)
        logger.setLevel(previous_level)


def _only_prompt_eval(records: list[logging.LogRecord]) -> list[logging.LogRecord]:
    """Filter to the prompt-eval event."""
    return [r for r in records if getattr(r, "event", None) == PROMPT_EVAL_LOG_EVENT]


@pytest.mark.asyncio
async def test_generate_structured_logs_prompt_eval_count_from_the_backend_reply(
    monkeypatch: pytest.MonkeyPatch, prompt_eval_records: list[logging.LogRecord]
) -> None:
    """The backend's own token count reaches the log, alongside the window it ran under."""
    adapter = _adapter(monkeypatch, prompt_eval_count=_PROMPT_EVAL_COUNT, eval_count=_EVAL_COUNT)
    await adapter.generate_structured(
        prompt=_PROMPT_TEXT, schema={}, max_tokens=512, system=_SYSTEM_TEXT
    )

    records = _only_prompt_eval(prompt_eval_records)
    assert len(records) == 1
    record = records[0]
    assert record.prompt_eval_count == _PROMPT_EVAL_COUNT
    assert record.eval_count == _EVAL_COUNT
    assert record.num_ctx == get_settings().OLLAMA_CONTEXT_LENGTH
    assert record.num_predict == 512
    assert record.prompt_chars == len(_PROMPT_TEXT)
    assert record.system_chars == len(_SYSTEM_TEXT)
    assert record.model == "qwen2.5:7b"


@pytest.mark.asyncio
async def test_generate_logs_prompt_eval_count(
    monkeypatch: pytest.MonkeyPatch, prompt_eval_records: list[logging.LogRecord]
) -> None:
    """The plain-text path reports the same evidence as the structured one."""
    adapter = _adapter(monkeypatch, prompt_eval_count=_PROMPT_EVAL_COUNT)
    await adapter.generate(prompt=_PROMPT_TEXT, max_tokens=256, temperature=0.15)

    records = _only_prompt_eval(prompt_eval_records)
    assert len(records) == 1
    assert records[0].prompt_eval_count == _PROMPT_EVAL_COUNT
    assert records[0].num_predict == 256
    assert records[0].system_chars == 0


@pytest.mark.asyncio
async def test_a_reply_without_prompt_eval_count_still_returns_and_logs_none(
    monkeypatch: pytest.MonkeyPatch, prompt_eval_records: list[logging.LogRecord]
) -> None:
    """The field is not guaranteed by the backend contract, so its absence is not an error."""
    adapter = _adapter(monkeypatch)
    result = await adapter.generate_structured(prompt=_PROMPT_TEXT, schema={}, max_tokens=512)

    assert result == {"ok": True}
    records = _only_prompt_eval(prompt_eval_records)
    assert len(records) == 1
    assert records[0].prompt_eval_count is None
