"""
test_context_budget_enforcer_v14.py - Unit tests for tier-aware context budget enforcement.

Does NOT: execute graph/LLM calls.

Dependencies injected: none.
"""

import pytest

from npc_engine.retrieval.context_budget_enforcer import (
    ContextBudgetError,
    ContextCompressionCache,
    build_compression_cache_key,
    enforce_context_budget,
)
from npc_engine.retrieval.context_merger import ContextItem, MergedContext
from npc_engine.schema.llm_config_models import LLMConfig, RelevanceWeights, TierBudgetTokens


def _llm_config() -> LLMConfig:
    return LLMConfig(
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
        tier_budget_tokens=TierBudgetTokens(tier_a=60, tier_b=40, tier_c=20),
        session_turns_budget_tokens=20,
        compression_trigger_ratio=0.5,
        max_proximity_hops=2,
        relevance_weights=RelevanceWeights(
            recency=0.25,
            severity=0.20,
            proximity=0.20,
            relation=0.20,
            quest=0.10,
            explicit=0.05,
        ),
    )


def test_enforce_context_budget_raises_typed_error_when_tier_a_overflow() -> None:
    context = MergedContext(
        items=[
            ContextItem(key="world", text="w" * 40, tier="tier0", priority=100),
            ContextItem(key="session", text="s" * 500, tier="tierA", priority=95),
        ]
    )

    with pytest.raises(ContextBudgetError) as error:
        enforce_context_budget(context=context, llm_config=_llm_config())

    assert error.value.tier == "tier_a"
    assert error.value.used_tokens > error.value.budget_tokens


def test_enforce_context_budget_never_compresses_tier_a_or_session() -> None:
    context = MergedContext(
        items=[
            ContextItem(key="world", text="w" * 20, tier="tier0", priority=100),
            ContextItem(key="session", text="s" * 20, tier="tierA", priority=95),
            ContextItem(key="character:npc_1", text='{"id":"npc_1"}', tier="tierA", priority=90),
            ContextItem(key="rag:1", text='{"summary":"x"}' * 20, tier="tierB", priority=10),
        ]
    )
    compression_cache = ContextCompressionCache()

    enforce_context_budget(context=context, llm_config=_llm_config(), compression_cache=compression_cache)

    assert len(compression_cache.entries) == 1


def test_enforce_context_budget_compresses_tier_b_when_trigger_exceeded() -> None:
    context = MergedContext(
        items=[
            ContextItem(key="world", text="w" * 20, tier="tier0", priority=100),
            ContextItem(key="session", text="s" * 20, tier="tierA", priority=95),
            ContextItem(key="rag:2", text='{"summary":"big"}' * 40, tier="tierB", priority=10),
        ]
    )
    compression_cache = ContextCompressionCache()

    trimmed = enforce_context_budget(context=context, llm_config=_llm_config(), compression_cache=compression_cache)
    rag_item = next(item for item in trimmed.items if item.key == "rag:2")

    assert len(rag_item.text) < len('{"summary":"big"}' * 40)
    assert len(compression_cache.entries) == 1


def test_build_compression_cache_key_uses_expected_dimensions_only() -> None:
    key_one = build_compression_cache_key(
        node_id="npc_1",
        node_type="character",
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
    )
    key_two = build_compression_cache_key(
        node_id="npc_1",
        node_type="character",
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
    )

    assert key_one == key_two


def test_compression_cache_invalidates_when_graph_timestamp_changes() -> None:
    cache = ContextCompressionCache()
    item = ContextItem(
        key="character:npc_1",
        text='{"id":"npc_1","last_graph_updated_at":"2026-04-16T10:00:00Z","summary":"'
        + ("A" * 600)
        + '"}',
        tier="tierB",
        priority=10,
    )
    llm_config = _llm_config()

    first = cache.compress_item(item=item, llm_config=llm_config, target_tokens=8)
    second = cache.compress_item(item=item, llm_config=llm_config, target_tokens=8)
    changed_item = item.model_copy(
        update={"text": item.text.replace("2026-04-16T10:00:00Z", "2026-04-16T11:00:00Z")}
    )
    third = cache.compress_item(item=changed_item, llm_config=llm_config, target_tokens=8)

    assert first == second
    assert third != second


def test_compression_cache_invalidates_when_source_changes_with_same_timestamp() -> None:
    cache = ContextCompressionCache()
    llm_config = _llm_config()
    base = ContextItem(
        key="character:npc_1",
        text='{"id":"npc_1","last_graph_updated_at":"2026-04-16T10:00:00Z","summary":"'
        + ("A" * 600)
        + '"}',
        tier="tierB",
        priority=10,
    )
    changed = ContextItem(
        key="character:npc_1",
        text='{"id":"npc_1","last_graph_updated_at":"2026-04-16T10:00:00Z","summary":"'
        + ("B" * 600)
        + '"}',
        tier="tierB",
        priority=10,
    )

    first = cache.compress_item(item=base, llm_config=llm_config, target_tokens=8)
    second = cache.compress_item(item=changed, llm_config=llm_config, target_tokens=8)

    assert first != second