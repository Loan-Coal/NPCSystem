"""
Module: test_context_pinned_pool
Layer: tests/unit
Purpose: Verify pinned-core + ranked-pool fill in context budget enforcer (EXP-30).
Dependencies: context_merger, context_budget_enforcer, context_config_models
Used by: pytest test runner
"""

from __future__ import annotations

import pytest

from npc_engine.retrieval.context_budget_enforcer import (
    enforce_context_budget,
    fill_to_budget,
)
from npc_engine.retrieval.context_merger import ContextItem, MergedContext
from npc_engine.schema.context_config_models import LLMConfig, RelevanceWeights, TierBudgetTokens


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _llm_config(tier_a: int = 60, tier_b: int = 40, tier_c: int = 20) -> LLMConfig:
    """Return a minimal LLMConfig suitable for unit tests."""
    return LLMConfig(
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
        tier_budget_tokens=TierBudgetTokens(tier_a=tier_a, tier_b=tier_b, tier_c=tier_c),
        session_turns_budget_tokens=50,
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


def _short(text: str, tokens: int) -> str:
    """Return a string of approximately `tokens` tokens (4 chars each)."""
    return text * (tokens * 4)


def _pinned_core_items(npc_id: str = "npc_1") -> list[ContextItem]:
    """Build the five pinned core items that must always survive budget enforcement."""
    return [
        ContextItem(key="world", text=_short("w", 5), tier="tier0", priority=100, pinned=True),
        ContextItem(key="emotion", text=_short("e", 5), tier="tier0", priority=95, pinned=True),
        ContextItem(key=f"character:{npc_id}", text=_short("c", 5), tier="tierA", priority=100, pinned=True),
        ContextItem(key="session", text=_short("s", 5), tier="tierA", priority=99, pinned=True),
        ContextItem(key="active_quest", text=_short("q", 5), tier="tierA", priority=89, pinned=True),
    ]


def _over_budget_context(npc_id: str = "npc_1") -> MergedContext:
    """Build a context whose non-pinned tier-A items exceed the tier-A budget.

    Pinned tier-A items use ~5 tokens each (session + character + active_quest = ~15 tokens).
    Non-pinned tier-A items fill 300 tokens total — far above the 60-token tier_a budget.
    """
    pinned = _pinned_core_items(npc_id)
    non_pinned_tier_a = [
        ContextItem(key="memories", text=_short("m", 40), tier="tierA", priority=90, pinned=False),
        ContextItem(key="beliefs", text=_short("b", 40), tier="tierA", priority=88, pinned=False),
        ContextItem(key="goals", text=_short("g", 40), tier="tierA", priority=87, pinned=False),
        ContextItem(key="owned_items", text=_short("i", 40), tier="tierA", priority=86, pinned=False),
        ContextItem(key="secrets", text=_short("x", 40), tier="tierA", priority=84, pinned=False),
        # lowest priority — should be dropped first
        ContextItem(key="obligations", text=_short("o", 40), tier="tierA", priority=83, pinned=False),
    ]
    return MergedContext(items=[*pinned, *non_pinned_tier_a])


# ---------------------------------------------------------------------------
# enforce_context_budget tests
# ---------------------------------------------------------------------------

class TestEnforceContextBudgetPinnedPool:
    """Tests for pinned-core + ranked-pool policy in enforce_context_budget."""

    def test_does_not_raise_when_non_pinned_tier_a_overflows(self) -> None:
        """Enforcer must NOT raise even when non-pinned tier-A exceeds budget."""
        context = _over_budget_context()
        # Should complete without raising ContextBudgetError
        result = enforce_context_budget(context=context, llm_config=_llm_config())
        assert result is not None

    def test_all_pinned_items_present_in_output(self) -> None:
        """Every pinned item (world, emotion, character, session, active_quest) survives."""
        context = _over_budget_context()
        result = enforce_context_budget(context=context, llm_config=_llm_config())
        output_keys = {item.key for item in result.items}
        assert "world" in output_keys
        assert "emotion" in output_keys
        assert "character:npc_1" in output_keys
        assert "session" in output_keys
        assert "active_quest" in output_keys

    def test_low_priority_non_pinned_item_dropped(self) -> None:
        """At least one low-priority non-pinned item is dropped when budget is tight."""
        context = _over_budget_context()
        result = enforce_context_budget(context=context, llm_config=_llm_config())
        output_keys = {item.key for item in result.items}
        # obligations has priority=83, the lowest among non-pinned items
        assert "obligations" not in output_keys

    def test_total_tokens_within_budget(self) -> None:
        """Total tier-A token count must not exceed the configured tier-A budget."""
        from npc_engine.retrieval.context_utils import estimate_tokens

        config = _llm_config()
        context = _over_budget_context()
        result = enforce_context_budget(context=context, llm_config=config)
        tier_a_tokens = sum(
            estimate_tokens(item.text)
            for item in result.items
            if item.tier == "tierA"
        )
        assert tier_a_tokens <= config.tier_budget_tokens.tier_a

    def test_higher_priority_non_pinned_items_kept_before_lower(self) -> None:
        """When budget is tight, higher-priority non-pinned items survive over lower ones."""
        context = _over_budget_context()
        result = enforce_context_budget(context=context, llm_config=_llm_config())
        output_keys = {item.key for item in result.items}
        # memories (priority=90) should survive if obligations (83) was dropped
        if "obligations" not in output_keys:
            assert "memories" in output_keys


# ---------------------------------------------------------------------------
# fill_to_budget tests
# ---------------------------------------------------------------------------

class TestFillToBudgetPinnedPool:
    """Tests for pinned-core + ranked-pool policy in fill_to_budget."""

    def test_does_not_raise_when_non_pinned_tier_a_overflows(self) -> None:
        """fill_to_budget must not raise when non-pinned tier-A exceeds budget."""
        context = _over_budget_context()
        config = _llm_config()
        result, serialized = fill_to_budget(
            context=context,
            llm_config=config,
            prompt_token_budget=200,
        )
        assert result is not None
        assert isinstance(serialized, str)

    def test_all_pinned_items_present_after_fill(self) -> None:
        """fill_to_budget keeps all pinned items even when total budget is tight."""
        context = _over_budget_context()
        result, _ = fill_to_budget(
            context=context,
            llm_config=_llm_config(),
            prompt_token_budget=200,
        )
        output_keys = {item.key for item in result.items}
        assert "world" in output_keys
        assert "emotion" in output_keys
        assert "character:npc_1" in output_keys
        assert "session" in output_keys
        assert "active_quest" in output_keys

    def test_low_priority_non_pinned_item_dropped_in_fill(self) -> None:
        """fill_to_budget drops low-priority non-pinned items before any pinned item."""
        context = _over_budget_context()
        result, _ = fill_to_budget(
            context=context,
            llm_config=_llm_config(),
            prompt_token_budget=200,
        )
        output_keys = {item.key for item in result.items}
        # obligations has the lowest priority and should be dropped
        assert "obligations" not in output_keys

    def test_total_tokens_within_prompt_budget(self) -> None:
        """Serialized output must not exceed the prompt_token_budget."""
        from npc_engine.retrieval.context_utils import estimate_tokens

        context = _over_budget_context()
        prompt_budget = 200
        _, serialized = fill_to_budget(
            context=context,
            llm_config=_llm_config(),
            prompt_token_budget=prompt_budget,
        )
        assert estimate_tokens(serialized) <= prompt_budget
