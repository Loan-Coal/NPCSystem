"""
test_llm_metrics_observability_v14.py - Tests dialogue LLM metrics emission.

Does NOT: call external LLM backends.

Dependencies injected: Fake LLM client.
"""

from pathlib import Path
from typing import Any, AsyncIterator

import pytest

_FALLBACK_PATH = str(Path(__file__).resolve().parents[2] / "src" / "npc_engine" / "data" / "fallback_responses.json")

from npc_engine.engines.dialogue.llm_client import DialogueLLMClient
from npc_engine.utils.errors import LLMRequestError
from npc_engine.utils.metrics import get_counter_value, reset_metrics_registry


class FakeLLMClient:
    """Deterministic fake LLM client for metric tests."""

    async def generate(self, prompt: str, max_tokens: int, temperature: float, top_p=None, stop_sequences=None, system=None) -> str:
        return "ok"

    async def generate_structured(self, prompt: str, schema: dict[str, Any], max_tokens: int, top_p=None, stop_sequences=None, system=None) -> dict[str, Any]:
        return {
            "npc_response": "I hear you.",
            "relation_deltas": {"trust": 0, "fear": 0, "affection": 0},
            "mood_update": None,
            "action": {"type": "speak", "target_id": None, "parameters": {}},
            "facial_expression": {"type": "neutral", "intensity": 20},
        }

    async def stream(self, prompt: str, max_tokens: int, temperature: float, top_p=None, stop_sequences=None, system=None) -> AsyncIterator[str]:
        yield "hello "
        yield "world"

    def model_name(self) -> str:
        return "mock"


class RequestErrorLLMClient(FakeLLMClient):
    """Fake LLM client that simulates structured request failures."""

    async def generate_structured(self, prompt: str, schema: dict[str, Any], max_tokens: int, top_p=None, stop_sequences=None, system=None) -> dict[str, Any]:
        raise LLMRequestError(model="mock", detail="backend_unavailable")


class InvalidStructuredLLMClient(FakeLLMClient):
    """Fake LLM client that returns invalid structured payload shape."""

    async def generate_structured(self, prompt: str, schema: dict[str, Any], max_tokens: int, top_p=None, stop_sequences=None, system=None) -> dict[str, Any]:
        return {
            "npc_response": "still speaking",
            "relation_deltas": {"trust": 0, "fear": 0, "affection": 0},
            "mood_update": None,
            "action": {"type": "invalid_action", "target_id": None, "parameters": {}},
            "facial_expression": {"type": "neutral", "intensity": 200},
        }


def setup_function() -> None:
    reset_metrics_registry()


@pytest.mark.asyncio
async def test_dialogue_llm_client_emits_call_and_token_metrics() -> None:
    """Structured LLM generation should emit call and token counters."""

    client = DialogueLLMClient(llm_client=FakeLLMClient(), fallback_path=_FALLBACK_PATH, max_tokens=512, temperature=0.7, top_p=0.95, stop_sequences=[])

    await client.generate_response(prompt="player says hello")

    calls = get_counter_value("llm_calls_total", labels={"engine": "dialogue", "backend": "mock", "mode": "structured"})
    tokens_in = get_counter_value(
        "llm_tokens_in_total", labels={"engine": "dialogue", "backend": "mock", "mode": "structured"}
    )
    tokens_out = get_counter_value(
        "llm_tokens_out_total", labels={"engine": "dialogue", "backend": "mock", "mode": "structured"}
    )

    assert calls == 1.0
    assert tokens_in > 0.0
    assert tokens_out > 0.0


@pytest.mark.asyncio
async def test_dialogue_llm_stream_emits_call_and_token_metrics() -> None:
    """Stream mode should emit LLM call and token counters."""

    client = DialogueLLMClient(llm_client=FakeLLMClient(), fallback_path=_FALLBACK_PATH, max_tokens=512, temperature=0.7, top_p=0.95, stop_sequences=[])

    chunks = await client.stream_text(prompt="stream prompt")

    calls = get_counter_value("llm_calls_total", labels={"engine": "dialogue", "backend": "mock", "mode": "stream"})
    tokens_out = get_counter_value(
        "llm_tokens_out_total", labels={"engine": "dialogue", "backend": "mock", "mode": "stream"}
    )

    assert calls == 1.0
    assert len(chunks) == 2
    assert tokens_out > 0.0


@pytest.mark.asyncio
async def test_dialogue_llm_generate_response_falls_back_on_request_error() -> None:
    """Structured request failures should produce deterministic fallback payloads."""

    client = DialogueLLMClient(llm_client=RequestErrorLLMClient(), fallback_path=_FALLBACK_PATH, max_tokens=512, temperature=0.7, top_p=0.95, stop_sequences=[])

    response = await client.generate_response(prompt="player says hello")

    assert response["npc_response"] == "I need a moment to think."
    assert response["action"]["type"] == "speak"
    fallback_tokens = get_counter_value(
        "llm_tokens_out_total",
        labels={"engine": "dialogue", "backend": "mock", "mode": "structured", "fallback": "request_error"},
    )
    assert fallback_tokens > 0.0


@pytest.mark.asyncio
async def test_dialogue_llm_generate_response_falls_back_on_invalid_structured_payload() -> None:
    """Invalid structured payloads should degrade to fallback dialogue responses."""

    client = DialogueLLMClient(llm_client=InvalidStructuredLLMClient(), fallback_path=_FALLBACK_PATH, max_tokens=512, temperature=0.7, top_p=0.95, stop_sequences=[])

    response = await client.generate_response(prompt="player says hello")

    assert response["npc_response"] == "I need a moment to think."
    assert response["facial_expression"]["intensity"] == 20
    fallback_tokens = get_counter_value(
        "llm_tokens_out_total",
        labels={"engine": "dialogue", "backend": "mock", "mode": "structured", "fallback": "validation_error"},
    )
    assert fallback_tokens > 0.0
