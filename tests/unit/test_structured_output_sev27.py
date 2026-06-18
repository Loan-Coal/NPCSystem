"""
Module: test_structured_output_sev27
Layer: tests/unit
Purpose: Verify SEV-27 fixes: temperature 0.1 in Ollama payload, repair retry on
         ValidationError, and canned fallback served only after both attempts fail.
Dependencies: npc_engine.engines.llm.mock_adapter, npc_engine.engines.dialogue.llm_client,
              npc_engine.engines.llm.ollama_adapter
Used by: pytest unit test suite
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FALLBACK_PATH = str(_REPO_ROOT / "src" / "npc_engine" / "data" / "fallback_responses.json")

from npc_engine.engines.dialogue.llm_client import DialogueLLMClient
from npc_engine.engines.llm.mock_adapter import MockLLMAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_STRUCTURED_RESPONSE: dict[str, Any] = {
    "npc_response": "Hello traveller.",
    "relation_deltas": {"trust": 1, "fear": 0, "affection": 0},
    "mood_update": None,
    "action": {"type": "speak", "target_id": None, "parameters": {}},
    "facial_expression": {"type": "neutral", "intensity": 20},
}


def _make_client(adapter: MockLLMAdapter) -> DialogueLLMClient:
    """Construct a DialogueLLMClient wired to the given adapter."""
    return DialogueLLMClient(
        llm_client=adapter,
        fallback_path=_FALLBACK_PATH,
        max_tokens=256,
        temperature=0.7,
        top_p=0.95,
        stop_sequences=[],
        log_prompts=False,
    )


# ---------------------------------------------------------------------------
# Test: fail_first_call — retry succeeds, canned fallback NOT served
# ---------------------------------------------------------------------------


def _msgs(mock_call_list: Any) -> list[str]:
    """Extract the first positional arg (log message) from each recorded log call."""
    return [call.args[0] for call in mock_call_list if call.args]


@pytest.mark.asyncio
async def test_retry_succeeds_on_first_call_failure() -> None:
    """fail_first_call=True: second attempt succeeds; canned fallback must NOT be served.

    Patches the module logger directly rather than using caplog: utils/logging.py
    sets propagate=False on the engine logger, so caplog captures nothing once
    logging is configured by another test (L4-01 ordering flake).
    """
    adapter = MockLLMAdapter(
        response=_VALID_STRUCTURED_RESPONSE,
        fail_first_call=True,
    )
    client = _make_client(adapter)

    with patch("npc_engine.engines.dialogue.llm_client.logger") as mock_logger:
        result = await client.generate_response(prompt="Hello")

    # The second attempt should have returned the valid response.
    assert result["npc_response"] == "Hello traveller."

    # Exactly one WARNING (the failed first attempt).
    validation_warnings = [m for m in _msgs(mock_logger.warning.call_args_list) if "structured_output_validation_failed" in m]
    assert len(validation_warnings) == 1, f"Expected 1 validation warning, got: {_msgs(mock_logger.warning.call_args_list)}"

    # No fallback ERROR (fallback was not served).
    fallback_errors = [m for m in _msgs(mock_logger.error.call_args_list) if "structured_output_fallback_served" in m]
    assert len(fallback_errors) == 0, f"Canned fallback was unexpectedly served: {_msgs(mock_logger.error.call_args_list)}"


# ---------------------------------------------------------------------------
# Test: return_garbage — both attempts fail; canned fallback IS served
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_canned_fallback_served_when_both_attempts_fail() -> None:
    """return_garbage=True: both attempts return unparseable dict; fallback IS served."""
    adapter = MockLLMAdapter(
        response=_VALID_STRUCTURED_RESPONSE,
        return_garbage=True,
    )
    client = _make_client(adapter)

    with patch("npc_engine.engines.dialogue.llm_client.logger") as mock_logger:
        result = await client.generate_response(prompt="Hello")

    # Canned fallback payload should be returned.
    assert result["npc_response"] == "I need a moment to think."

    # Two WARNINGs — one per failed attempt.
    validation_warnings = [m for m in _msgs(mock_logger.warning.call_args_list) if "structured_output_validation_failed" in m]
    assert len(validation_warnings) == 2, f"Expected 2 validation warnings, got: {_msgs(mock_logger.warning.call_args_list)}"

    # One ERROR — fallback served after exhausting retries.
    fallback_errors = [m for m in _msgs(mock_logger.error.call_args_list) if "structured_output_fallback_served" in m]
    assert len(fallback_errors) == 1, f"Expected 1 fallback error, got: {_msgs(mock_logger.error.call_args_list)}"


# ---------------------------------------------------------------------------
# Test: Ollama payload includes temperature 0.1 in structured call
# ---------------------------------------------------------------------------


class _CapturingOllamaClient:
    """Records the last payload posted by OllamaAdapter."""

    def __init__(self, timeout: float) -> None:
        self.last_payload: dict[str, Any] = {}

    async def __aenter__(self) -> _CapturingOllamaClient:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    async def post(self, url: str, json: dict[str, Any]) -> "_FakeResponse":
        self.last_payload = json
        return _FakeResponse(payload={"response": '{"ok": true}'})

    async def aclose(self) -> None:
        pass


class _FakeResponse:
    """Minimal HTTP response stub."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict[str, Any]:
        return self._payload


_capturing_instance: _CapturingOllamaClient | None = None


def _capturing_factory(timeout: float) -> _CapturingOllamaClient:
    global _capturing_instance
    _capturing_instance = _CapturingOllamaClient(timeout)
    return _capturing_instance


@pytest.mark.asyncio
async def test_ollama_generate_structured_uses_temperature_01(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ollama generate_structured must set temperature=0.1 (STRUCTURED_OUTPUT_TEMPERATURE)."""
    import npc_engine.engines.llm.ollama_adapter as _mod

    monkeypatch.setattr(_mod.httpx, "AsyncClient", _capturing_factory)

    from npc_engine.engines.llm.ollama_adapter import OllamaAdapter

    adapter = OllamaAdapter(base_url="http://fake", model_name="qwen2.5:14b", timeout_seconds=1.0)
    await adapter.generate_structured(prompt="p", schema={"type": "object"}, max_tokens=64)

    assert _capturing_instance is not None
    options = _capturing_instance.last_payload["options"]
    assert "temperature" in options, "temperature key missing from Ollama payload options"
    assert options["temperature"] == pytest.approx(0.1), (
        f"Expected temperature=0.1, got {options['temperature']}"
    )


@pytest.mark.asyncio
async def test_ollama_generate_structured_passes_schema_as_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ollama generate_structured must pass the schema dict as the 'format' field (not 'json')."""
    import npc_engine.engines.llm.ollama_adapter as _mod

    monkeypatch.setattr(_mod.httpx, "AsyncClient", _capturing_factory)

    from npc_engine.engines.llm.ollama_adapter import OllamaAdapter

    schema = {"type": "object", "properties": {"npc_response": {"type": "string"}}}
    adapter = OllamaAdapter(base_url="http://fake", model_name="qwen2.5:14b", timeout_seconds=1.0)
    await adapter.generate_structured(prompt="p", schema=schema, max_tokens=64)

    assert _capturing_instance is not None
    assert _capturing_instance.last_payload.get("format") == schema, (
        f"Expected format={schema!r}, got {_capturing_instance.last_payload.get('format')!r}"
    )
