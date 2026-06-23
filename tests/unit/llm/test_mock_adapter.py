"""
test_mock_adapter.py - Unit tests for deterministic mock LLM adapter behavior.

Does NOT: contact network services.

Dependencies injected: None.
"""

import pytest

from npc_engine.engines.llm.mock_adapter import MockLLMAdapter


@pytest.mark.asyncio
async def test_mock_adapter_stream_and_structured_output() -> None:
    adapter = MockLLMAdapter(response={"npc_response": "hello world", "relation_deltas": {"trust": 1}})
    structured = await adapter.generate_structured(prompt="p", schema={}, max_tokens=10)
    assert structured["npc_response"] == "hello world"

    streamed_tokens = []
    async for token in adapter.stream(prompt="p", max_tokens=10, temperature=0.1):
        streamed_tokens.append(token)
    assert "hello " in streamed_tokens
    assert "world " in streamed_tokens
