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


# ---------------------------------------------------------------------------
# seed parity (EVAL-P20.0 / DEC-176)
#
# CLAUDE.md's LSP rule: a mock that silently ignores seed while the real adapter
# honours it is an invalid mock and produces false-passing tests.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_records_seed_and_returns_identical_output() -> None:
    adapter = MockLLMAdapter(response={"npc_response": "steady"})
    first = await adapter.generate_structured(prompt="p", schema={}, max_tokens=10, seed=7)
    second = await adapter.generate_structured(prompt="p", schema={}, max_tokens=10, seed=7)

    assert first == second
    assert adapter.seeds_seen == (7, 7)
    assert adapter.last_seed == 7


@pytest.mark.asyncio
async def test_mock_records_seed_across_every_generation_surface() -> None:
    adapter = MockLLMAdapter(response={"npc_response": "steady"})
    await adapter.generate(prompt="p", max_tokens=10, temperature=0.1, seed=1)
    await adapter.generate_structured(prompt="p", schema={}, max_tokens=10, seed=2)
    async for _ in adapter.stream(prompt="p", max_tokens=10, temperature=0.1, seed=3):
        pass

    assert adapter.seeds_seen == (1, 2, 3)


@pytest.mark.asyncio
async def test_mock_last_seed_is_none_when_unseeded() -> None:
    adapter = MockLLMAdapter()
    await adapter.generate(prompt="p", max_tokens=10, temperature=0.1)

    assert adapter.seeds_seen == (None,)
    assert adapter.last_seed is None
