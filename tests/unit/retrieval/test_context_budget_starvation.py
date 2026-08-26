"""
Module: test_context_budget_starvation
Layer: tests/unit
Purpose: Regression tests for ISSUE-145 — budget enforcement silently starves pinned
         and tail context items, producing empty NPC profiles at the prompt (RET-P0.1).
Dependencies: context_merger, context_budget_enforcer, context_config_models
Used by: pytest test runner
"""

from __future__ import annotations

from npc_engine.retrieval.context import ContextItem, MergedContext, fill_to_budget
from npc_engine.schema.context_config_models import (
    LLMConfig,
    RelevanceWeights,
    TierBudgetTokens,
)

# Production-shaped constants: the YAML sets tier budgets far above the fraction-derived
# caps, so the fraction (0.55 of prompt budget) is what actually binds — as in production.
PRODUCTION_TIER_A_BUDGET = 4000
PRODUCTION_TIER_B_BUDGET = 3000
PRODUCTION_TIER_C_BUDGET = 2000
PRODUCTION_PROMPT_BUDGET = 512

OVERSIZED_TIER_A_TOKENS = PRODUCTION_PROMPT_BUDGET + 100
"""Larger than the WHOLE prompt budget, so no tier-A allocation can ever admit it.

Previously 300, which was oversized only against the 281-token fraction cap a 512-token
budget used to yield. P4 reclaims the share tiers B and C do not spend, lifting that cap to
502 -- at which point a 300-token item fits and neither test below exercised the skip path
any more. Sizing against the budget instead of against the cap makes these independent of
how tier A is allocated, which is what they were always about.
"""


def _llm_config() -> LLMConfig:
    """Return an LLMConfig with production-shaped tier budgets."""
    return LLMConfig(
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
        tier_budget_tokens=TierBudgetTokens(
            tier_a=PRODUCTION_TIER_A_BUDGET,
            tier_b=PRODUCTION_TIER_B_BUDGET,
            tier_c=PRODUCTION_TIER_C_BUDGET,
        ),
        session_turns_budget_tokens=1200,
        compression_trigger_ratio=0.85,
        max_proximity_hops=2,
        relevance_weights=RelevanceWeights(
            recency=0.30,
            severity=0.20,
            proximity=0.20,
            relation=0.20,
            quest=0.10,
        ),
    )


def _sized(marker: str, tokens: int) -> str:
    """Return a string estimating to exactly `tokens` tokens (4 chars per token)."""
    return marker * (tokens * 4)


def _keys(context: MergedContext) -> set[str]:
    """Return the key set of a merged context."""
    return {item.key for item in context.items}


class TestPinnedItemsSurviveBudgetPressure:
    """ISSUE-145: a pinned item must never be dropped for budget reasons."""

    def test_pinned_character_survives_when_tier0_consumes_most_of_budget(self) -> None:
        """The pinned character node must reach the prompt even when tier0 is large.

        Reproduces the `profile: {}` half of ISSUE-145: with tier0 at 360 tokens and a
        512-token budget, a 153-token pinned character node pushes `running` past the
        budget, and the tier-A fill loop drops it instead of exempting it.
        """
        context = MergedContext(
            items=[
                ContextItem(key="world", text=_sized("w", 200), tier="tier0", priority=100, pinned=True),
                ContextItem(key="emotion", text=_sized("e", 160), tier="tier0", priority=95, pinned=True),
                ContextItem(
                    key="character:mira_innkeeper",
                    text=_sized("c", 153),
                    tier="tierA",
                    priority=100,
                    pinned=True,
                ),
            ]
        )

        result, _ = fill_to_budget(
            context=context,
            llm_config=_llm_config(),
            prompt_token_budget=PRODUCTION_PROMPT_BUDGET,
        )

        assert "character:mira_innkeeper" in _keys(result)

    def test_pinned_session_survives_after_an_oversized_pinned_item(self) -> None:
        """A later pinned item is not collateral damage from an earlier one overflowing."""
        context = MergedContext(
            items=[
                ContextItem(key="world", text=_sized("w", 300), tier="tier0", priority=100, pinned=True),
                ContextItem(
                    key="character:mira_innkeeper",
                    text=_sized("c", 400),
                    tier="tierA",
                    priority=100,
                    pinned=True,
                ),
                ContextItem(key="session", text=_sized("s", 10), tier="tierA", priority=99, pinned=True),
            ]
        )

        result, _ = fill_to_budget(
            context=context,
            llm_config=_llm_config(),
            prompt_token_budget=PRODUCTION_PROMPT_BUDGET,
        )

        assert "session" in _keys(result)


class TestOversizedItemDoesNotTruncateTail:
    """ISSUE-145: one item that does not fit must not drop every item behind it."""

    def test_oversized_non_pinned_item_does_not_truncate_the_tail(self) -> None:
        """Smaller lower-priority items still fit after an oversized item is skipped.

        Reproduces the `beliefs: [] / goals: [] / memories: []` half of ISSUE-145: the
        non-pinned pool loop `break`s on the first item that does not fit rather than
        continuing to the smaller items behind it.
        """
        context = MergedContext(
            items=[
                ContextItem(key="world", text=_sized("w", 10), tier="tier0", priority=100, pinned=True),
                ContextItem(key="emotion", text=_sized("e", 10), tier="tier0", priority=95, pinned=True),
                ContextItem(
                    key="character:mira_innkeeper",
                    text=_sized("c", 10),
                    tier="tierA",
                    priority=100,
                    pinned=True,
                ),
                # Highest non-pinned priority AND too large to fit — must be skipped, not fatal.
                ContextItem(key="owned_items", text=_sized("i", OVERSIZED_TIER_A_TOKENS), tier="tierA", priority=95, pinned=False),
                ContextItem(key="memories", text=_sized("m", 20), tier="tierA", priority=90, pinned=False),
                ContextItem(key="beliefs", text=_sized("b", 20), tier="tierA", priority=88, pinned=False),
                ContextItem(key="goals", text=_sized("g", 20), tier="tierA", priority=87, pinned=False),
            ]
        )

        result, _ = fill_to_budget(
            context=context,
            llm_config=_llm_config(),
            prompt_token_budget=PRODUCTION_PROMPT_BUDGET,
        )

        surviving = _keys(result)
        assert "memories" in surviving
        assert "beliefs" in surviving
        assert "goals" in surviving

    def test_oversized_item_itself_is_still_dropped(self) -> None:
        """Skipping past an oversized item must not smuggle it into the output."""
        context = MergedContext(
            items=[
                ContextItem(key="world", text=_sized("w", 10), tier="tier0", priority=100, pinned=True),
                ContextItem(key="owned_items", text=_sized("i", OVERSIZED_TIER_A_TOKENS), tier="tierA", priority=95, pinned=False),
                ContextItem(key="goals", text=_sized("g", 20), tier="tierA", priority=87, pinned=False),
            ]
        )

        result, _ = fill_to_budget(
            context=context,
            llm_config=_llm_config(),
            prompt_token_budget=PRODUCTION_PROMPT_BUDGET,
        )

        assert "owned_items" not in _keys(result)


class TestIssue145EndToEndSymptom:
    """The exact reported symptom: a realistic NPC payload at the production budget."""

    def test_beliefs_goals_memories_survive_when_they_fit_the_tier_a_cap(self) -> None:
        """A context that fits the tier-A cap must not serialize to an empty NPC block.

        This is the ISSUE-145 acceptance shape: tier0 + pinned core + the three
        graph-authoritative collections, sized to fit the 281-token tier-A soft cap
        that a 512-token prompt budget yields.
        """
        context = MergedContext(
            items=[
                ContextItem(key="world", text=_sized("w", 90), tier="tier0", priority=100, pinned=True),
                ContextItem(key="emotion", text=_sized("e", 10), tier="tier0", priority=95, pinned=True),
                ContextItem(
                    key="character:mira_innkeeper",
                    text=_sized("c", 100),
                    tier="tierA",
                    priority=100,
                    pinned=True,
                ),
                ContextItem(key="session", text=_sized("s", 40), tier="tierA", priority=99, pinned=True),
                ContextItem(key="relation:player", text=_sized("r", 25), tier="tierA", priority=95, pinned=False),
                ContextItem(key="memories", text=_sized("m", 40), tier="tierA", priority=90, pinned=False),
                ContextItem(key="beliefs", text=_sized("b", 40), tier="tierA", priority=88, pinned=False),
                ContextItem(key="goals", text=_sized("g", 30), tier="tierA", priority=87, pinned=False),
            ]
        )

        result, _ = fill_to_budget(
            context=context,
            llm_config=_llm_config(),
            prompt_token_budget=PRODUCTION_PROMPT_BUDGET,
        )

        surviving = _keys(result)
        assert "character:mira_innkeeper" in surviving, "ISSUE-145: profile came back empty"
        assert "memories" in surviving, "ISSUE-145: memories came back empty"
        assert "beliefs" in surviving, "ISSUE-145: beliefs came back empty"
        assert "goals" in surviving, "ISSUE-145: goals came back empty"


class TestTheFullNpcPayloadNowFitsTierA:
    """ISSUE-145's second cause -- the ceiling RET-P0 could not lift -- now measured.

    The predecessor of this class computed `153 + 60 + 25 + 40 + 40 + 40 > int(512 * 0.55)`
    from module-local literals. It never called fill_to_budget and never read Settings, so
    it could not have observed either change it claimed to pin: it stayed green through P1
    raising the context window and through P4 reclaiming the tier B/C share. Asserting
    arithmetic against arithmetic is not a tripwire.

    This asserts the behaviour instead: at the same 512-token budget, with tiers B and C
    empty as they are on every turn today, a full-sized NPC payload reaches the prompt.
    """

    def test_a_full_npc_payload_reaches_the_prompt_at_the_production_budget(self) -> None:
        """Red before P4: the 0.55 fraction capped tier A at 281 and the payload wants 358."""
        context = MergedContext(
            items=[
                ContextItem(key="world", text=_sized("w", 90), tier="tier0", priority=100, pinned=True),
                ContextItem(key="emotion", text=_sized("e", 10), tier="tier0", priority=95, pinned=True),
                ContextItem(
                    key="character:mira_innkeeper",
                    text=_sized("c", 153),
                    tier="tierA",
                    priority=100,
                    pinned=True,
                ),
                ContextItem(key="session", text=_sized("s", 60), tier="tierA", priority=99, pinned=True),
                ContextItem(key="relation:player", text=_sized("r", 25), tier="tierA", priority=95),
                ContextItem(key="memories", text=_sized("m", 40), tier="tierA", priority=90),
                ContextItem(key="beliefs", text=_sized("b", 40), tier="tierA", priority=88),
                ContextItem(key="goals", text=_sized("g", 40), tier="tierA", priority=87),
            ]
        )

        result, _ = fill_to_budget(
            context=context,
            llm_config=_llm_config(),
            prompt_token_budget=PRODUCTION_PROMPT_BUDGET,
        )

        surviving = _keys(result)
        for key in ("relation:player", "memories", "beliefs", "goals"):
            assert key in surviving, f"{key} did not survive the tier-A allocation"
