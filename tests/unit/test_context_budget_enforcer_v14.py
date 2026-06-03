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
    fill_to_budget,
)
from npc_engine.retrieval.context_merger import ContextItem, MergedContext
from npc_engine.schema.context_config_models import LLMConfig, RelevanceWeights, TierBudgetTokens


def _llm_config() -> LLMConfig:
    return LLMConfig(
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
        tier_budget_tokens=TierBudgetTokens(tier_a=60, tier_b=40, tier_c=20),
        session_turns_budget_tokens=20,
        compression_trigger_ratio=0.5,
        max_proximity_hops=2,
        relevance_weights=RelevanceWeights(
            recency=0.30,
            severity=0.20,
            proximity=0.20,
            relation=0.20,
            quest=0.10,
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
    # Use prose text (~5 chars/token with tiktoken, matching CHARS_PER_TOKEN_ESTIMATE=4 well
    # enough that the compressed item fits within the 40-token tier_b budget after truncation).
    long_text = "Lorem ipsum dolor sit amet consectetur adipiscing elit " * 15  # ~430 chars, ~85 tokens
    context = MergedContext(
        items=[
            ContextItem(key="world", text="w" * 20, tier="tier0", priority=100),
            ContextItem(key="session", text="s" * 20, tier="tierA", priority=95),
            ContextItem(key="rag:2", text=long_text, tier="tierB", priority=10),
        ]
    )
    compression_cache = ContextCompressionCache()

    trimmed = enforce_context_budget(context=context, llm_config=_llm_config(), compression_cache=compression_cache)
    rag_item = next(item for item in trimmed.items if item.key == "rag:2")

    assert len(rag_item.text) < len(long_text)
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
        text='{"name":"Aldric","last_graph_updated_at":"2026-04-16T10:00:00Z","biography":"'
        + ("A" * 600)
        + '"}',
        tier="tierB",
        priority=10,
    )
    llm_config = _llm_config()

    first = cache.compress_item(item=item, llm_config=llm_config, target_tokens=8)
    second = cache.compress_item(item=item, llm_config=llm_config, target_tokens=8)
    # Change both timestamp and biography content so the recomputed compressed text differs
    changed_item = item.model_copy(
        update={
            "text": item.text.replace("2026-04-16T10:00:00Z", "2026-04-16T11:00:00Z").replace(
                "A" * 600, "B" * 600
            )
        }
    )
    third = cache.compress_item(item=changed_item, llm_config=llm_config, target_tokens=8)

    assert first == second
    assert third != second


def test_compression_cache_invalidates_when_source_changes_with_same_timestamp() -> None:
    cache = ContextCompressionCache()
    llm_config = _llm_config()
    base = ContextItem(
        key="character:npc_1",
        text='{"name":"Aldric","last_graph_updated_at":"2026-04-16T10:00:00Z","biography":"'
        + ("A" * 600)
        + '"}',
        tier="tierB",
        priority=10,
    )
    changed = ContextItem(
        key="character:npc_1",
        text='{"name":"Aldric","last_graph_updated_at":"2026-04-16T10:00:00Z","biography":"'
        + ("B" * 600)
        + '"}',
        tier="tierB",
        priority=10,
    )

    first = cache.compress_item(item=base, llm_config=llm_config, target_tokens=8)
    second = cache.compress_item(item=changed, llm_config=llm_config, target_tokens=8)

    assert first != second


# ---------------------------------------------------------------------------
# 3.4 — Tier 0 cap
# ---------------------------------------------------------------------------


def test_enforce_context_budget_raises_when_tier0_exceeds_cap() -> None:
    """Tier 0 items that exceed 380 tokens must raise ContextBudgetError."""
    context = MergedContext(
        items=[
            # 400+ characters ≈ 100+ tokens (estimate_tokens uses ~4 chars/token)
            ContextItem(key="world", text="w" * 1600, tier="tier0", priority=100),
            ContextItem(key="session", text="s" * 10, tier="tierA", priority=95),
        ]
    )
    with pytest.raises(ContextBudgetError) as exc_info:
        enforce_context_budget(context=context, llm_config=_llm_config())

    assert exc_info.value.tier == "tier0"
    assert exc_info.value.used_tokens > exc_info.value.budget_tokens


def test_enforce_context_budget_passes_when_tier0_within_cap() -> None:
    """Tier 0 items within 380 tokens must not raise."""
    context = MergedContext(
        items=[
            ContextItem(key="world", text="w" * 40, tier="tier0", priority=100),
            ContextItem(key="emotion", text="e" * 20, tier="tier0", priority=95),
            ContextItem(key="session", text="s" * 10, tier="tierA", priority=90),
        ]
    )
    # Should not raise
    result = enforce_context_budget(context=context, llm_config=_llm_config())
    tier0_keys = [item.key for item in result.items if item.tier == "tier0"]
    assert "world" in tier0_keys
    assert "emotion" in tier0_keys


# ---------------------------------------------------------------------------
# fill_to_budget tests
# ---------------------------------------------------------------------------

def _llm_config_large() -> LLMConfig:
    """LLMConfig with larger budgets for fill_to_budget tests."""
    return LLMConfig(
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
        tier_budget_tokens=TierBudgetTokens(tier_a=4000, tier_b=3000, tier_c=2000),
        session_turns_budget_tokens=1000,
        compression_trigger_ratio=0.9,
        max_proximity_hops=2,
        relevance_weights=RelevanceWeights(
            recency=0.30,
            severity=0.20,
            proximity=0.20,
            relation=0.20,
            quest=0.10,
        ),
    )


def _make_item(key: str, tier: str, priority: int, chars: int = 40) -> ContextItem:
    return ContextItem(key=key, text=key[0] * chars, tier=tier, priority=priority)


def test_fill_to_budget_tight_budget_includes_top_priority_tier_a_only() -> None:
    """With a tight budget (800 tokens), only highest-priority tier_a items fit; no error raised."""
    context = MergedContext(
        items=[
            _make_item("world", "tier0", 100, chars=40),
            _make_item("session", "tierA", 95, chars=100),
            _make_item("character:npc_high", "tierA", 90, chars=100),
            _make_item("character:npc_low", "tierA", 10, chars=100),
            _make_item("rag:1", "tierB", 5, chars=200),
            _make_item("rag:2", "tierC", 3, chars=200),
        ]
    )
    llm_config = _llm_config_large()

    filled, serialized = fill_to_budget(context=context, llm_config=llm_config, prompt_token_budget=800)

    tier_keys = {item.key for item in filled.items}
    assert "world" in tier_keys
    assert "session" in tier_keys
    assert "character:npc_high" in tier_keys
    assert isinstance(serialized, str)
    assert len(serialized) > 0


def test_fill_to_budget_never_raises_for_budget_overflow() -> None:
    """fill_to_budget must not raise ContextBudgetError even when tier_a alone exceeds total budget."""
    context = MergedContext(
        items=[
            _make_item("world", "tier0", 100, chars=40),
            _make_item("session", "tierA", 95, chars=3200),
        ]
    )
    llm_config = _llm_config_large()

    filled, serialized = fill_to_budget(context=context, llm_config=llm_config, prompt_token_budget=800)

    assert any(item.tier == "tier0" for item in filled.items)
    assert isinstance(serialized, str)


def test_fill_to_budget_large_budget_includes_all_tiers() -> None:
    """With an 8000-token budget all tiers should be represented."""
    context = MergedContext(
        items=[
            _make_item("world", "tier0", 100, chars=40),
            _make_item("session", "tierA", 95, chars=100),
            _make_item("character:npc_1", "tierA", 90, chars=100),
            _make_item("rag:1", "tierB", 20, chars=100),
            _make_item("rag:2", "tierC", 10, chars=100),
        ]
    )
    llm_config = _llm_config_large()

    filled, serialized = fill_to_budget(context=context, llm_config=llm_config, prompt_token_budget=8000)

    tier_keys = {item.key for item in filled.items}
    assert "world" in tier_keys
    assert "session" in tier_keys
    assert "character:npc_1" in tier_keys
    assert "rag:1" in tier_keys
    assert "rag:2" in tier_keys


def test_fill_to_budget_tier_a_fraction_limits_tier_a_tokens() -> None:
    """Reducing tier_a_fraction should cause lower-priority tier_a items to be dropped."""
    from npc_engine.schema.context_config_models import TierBudgetTokens

    config_narrow_a = LLMConfig(
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
        tier_budget_tokens=TierBudgetTokens(tier_a=4000, tier_b=3000, tier_c=2000),
        session_turns_budget_tokens=1000,
        compression_trigger_ratio=0.9,
        max_proximity_hops=2,
        relevance_weights=RelevanceWeights(
            recency=0.30, severity=0.20, proximity=0.20, relation=0.20, quest=0.10
        ),
        tier_a_fraction=0.10,
        tier_b_fraction=0.30,
    )
    context = MergedContext(
        items=[
            _make_item("world", "tier0", 100, chars=40),
            _make_item("session", "tierA", 95, chars=300),
            _make_item("character:npc_1", "tierA", 80, chars=300),
            _make_item("character:npc_2", "tierA", 60, chars=300),
            _make_item("character:npc_3", "tierA", 40, chars=300),
        ]
    )

    filled_narrow, _ = fill_to_budget(context=context, llm_config=config_narrow_a, prompt_token_budget=2000)
    filled_wide, _ = fill_to_budget(context=context, llm_config=_llm_config_large(), prompt_token_budget=2000)

    narrow_a_count = sum(1 for i in filled_narrow.items if i.tier == "tierA")
    wide_a_count = sum(1 for i in filled_wide.items if i.tier == "tierA")
    assert narrow_a_count < wide_a_count


def test_fill_to_budget_tier0_overflow_raises() -> None:
    """The only case fill_to_budget raises is when tier0 alone exceeds 380 tokens."""
    context = MergedContext(
        items=[
            _make_item("world", "tier0", 100, chars=1600),
        ]
    )
    llm_config = _llm_config_large()

    with pytest.raises(ContextBudgetError) as exc_info:
        fill_to_budget(context=context, llm_config=llm_config, prompt_token_budget=8000)

    assert exc_info.value.tier == "tier0"


def test_fill_to_budget_drops_lowest_priority_first() -> None:
    """When serialized size exceeds budget, tier_c is dropped before tier_b before tier_a.

    Uses "rag:" prefixed keys so items appear in npc_known_events in the serialized
    output and actually contribute to serialized size. The base skeleton with world/session
    fits in the budget; adding compressed rag items pushes over it, so the post-hoc trim
    drops tier_c first, then tier_b.
    """
    big = '{"summary":"' + "x" * 600 + '"}'  # valid JSON; after compression still ~90 chars in output
    context = MergedContext(
        items=[
            ContextItem(key="world", text='{"epoch":"war"}', tier="tier0", priority=100),
            ContextItem(key="session", text='["t1"]', tier="tierA", priority=95),
            ContextItem(key="rag:b1", text=big, tier="tierB", priority=20),
            ContextItem(key="rag:c1", text=big, tier="tierC", priority=10),
        ]
    )
    llm_config = _llm_config_large()

    # Budget=80: base skeleton+world+session ≈ 58 tokens (fits); adding a compressed rag
    # item (~90 chars in npc_known_events) pushes to ~81 tokens > 80, triggering the trim.
    filled, _ = fill_to_budget(context=context, llm_config=llm_config, prompt_token_budget=80)

    tier_keys = {item.key for item in filled.items}
    assert "world" in tier_keys
    assert "session" in tier_keys
    assert "rag:c1" not in tier_keys or "rag:b1" not in tier_keys