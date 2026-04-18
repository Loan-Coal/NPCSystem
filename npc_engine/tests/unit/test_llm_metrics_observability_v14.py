"""
test_llm_metrics_observability_v14.py - Tests dialogue LLM metrics emission.

Does NOT: call external LLM backends.

Dependencies injected: Fake LLM client.
"""

from typing import Any, AsyncIterator

import pytest

from engines.dialogue.llm_client import DialogueLLMClient
from utils.metrics import get_counter_value, reset_metrics_registry


class FakeLLMClient:
    """Deterministic fake LLM client for metric tests."""

    async def generate(self, prompt: str, max_tokens: int, temperature: float) -> str:
        return "ok"

    async def generate_structured(self, prompt: str, schema: dict[str, Any], max_tokens: int) -> dict[str, Any]:
        return {
            "npc_response": "I hear you.",
            "relation_deltas": {"trust": 0, "fear": 0, "affection": 0},
            "mood_update": None,
            "action": {"type": "speak", "target_id": None, "parameters": {}},
            "facial_expression": {"type": "neutral", "intensity": 20},
        }

    async def stream(self, prompt: str, max_tokens: int, temperature: float) -> AsyncIterator[str]:
        yield "hello "
        yield "world"

    def model_name(self) -> str:
        return "mock"


def setup_function() -> None:
    reset_metrics_registry()


@pytest.mark.asyncio
async def test_dialogue_llm_client_emits_call_and_token_metrics() -> None:
    """Structured LLM generation should emit call and token counters."""

    client = DialogueLLMClient(llm_client=FakeLLMClient(), fallback_path="data/fallback_responses.json")

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

    client = DialogueLLMClient(llm_client=FakeLLMClient(), fallback_path="data/fallback_responses.json")

    chunks = await client.stream_text(prompt="stream prompt")

    calls = get_counter_value("llm_calls_total", labels={"engine": "dialogue", "backend": "mock", "mode": "stream"})
    tokens_out = get_counter_value(
        "llm_tokens_out_total", labels={"engine": "dialogue", "backend": "mock", "mode": "stream"}
    )

    assert calls == 1.0
    assert len(chunks) == 2
    assert tokens_out > 0.0
