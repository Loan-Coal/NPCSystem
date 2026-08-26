"""
test_context_budget_reclaim.py - Tier A must get the budget tiers B and C do not spend.

ISSUE-197: `fill_to_budget` sized tier A at `min(tier_budget_tokens.tier_a,
prompt_token_budget * tier_a_fraction)` regardless of what tiers B and C were going to
use. With no vector corpus they use nothing, so 45% of every prompt budget was reserved
for tiers that spend zero while tier-A items were dropped for want of room. Measured live
2026-08-26: assembled context 564-742 tokens against a 1,312-token budget.

The guard half of this file matters more than the reclaim half. Giving tier A the
leftover must not let it eat the share tiers B and C will need once a corpus exists --
that share is the entire point of P7, and a fix that quietly takes it would make the
A/B arms unfalsifiable rather than merely wrong.

Does NOT: execute I/O, touch the graph, or call LLM services.
"""

from __future__ import annotations

import json

import pytest

from npc_engine.retrieval.context.context_budget_enforcer import (
    _fit_tier_a_pinned_pool,
    fill_to_budget,
    fill_to_budget_with_report,
)
from npc_engine.retrieval.context.context_merger import ContextItem, MergedContext
from npc_engine.retrieval.context.context_receipt import BudgetFillReport
from npc_engine.retrieval.context.context_utils import estimate_tokens
from npc_engine.schema.context_config_models import (
    LLMConfig,
    RelevanceWeights,
    TierBudgetTokens,
)

# Production-shaped: the YAML tier budgets sit far above the fraction-derived caps, so the
# fractions are what bind -- as in production. Budget 1000 keeps the arithmetic legible.
BUDGET = 1000
TIER_A_FRACTION = 0.55
TIER_B_FRACTION = 0.30
TIER_A_FLOOR = int(BUDGET * TIER_A_FRACTION)  # 550
TIER_B_CAP = int(BUDGET * TIER_B_FRACTION)  # 300
TIER_C_CAP = int(BUDGET * (1.0 - TIER_A_FRACTION - TIER_B_FRACTION))  # 150


def _llm_config(*, tier_a_budget: int = 4000) -> LLMConfig:
    return LLMConfig(
        prompt_schema_version="v1.4",
        compression_prompt_version="v1.4",
        tier_budget_tokens=TierBudgetTokens(tier_a=tier_a_budget, tier_b=3000, tier_c=2000),
        session_turns_budget_tokens=1200,
        compression_trigger_ratio=0.85,
        max_proximity_hops=2,
        relevance_weights=RelevanceWeights(
            recency=0.30, severity=0.20, proximity=0.20, relation=0.20, quest=0.10
        ),
        tier_a_fraction=TIER_A_FRACTION,
        tier_b_fraction=TIER_B_FRACTION,
    )


def _sized(marker: str, tokens: int) -> str:
    """A string estimating to exactly `tokens` tokens (estimate_tokens is len // 4)."""
    return marker * (tokens * 4)


def _tier_tokens(context: MergedContext, tier: str) -> int:
    return sum(estimate_tokens(i.text) for i in context.items if i.tier == tier)


def _keys(context: MergedContext) -> set[str]:
    return {i.key for i in context.items}


def _tier0() -> list[ContextItem]:
    """A realistic tier-0 block: 50 tokens, always pinned, never dropped."""
    return [
        ContextItem(key="world", text=_sized("w", 40), tier="tier0", priority=100, pinned=True),
        ContextItem(key="emotion", text=_sized("e", 10), tier="tier0", priority=95, pinned=True),
    ]


def _hungry_tier_a() -> list[ContextItem]:
    """Tier A wanting 800 tokens -- more than its 550 floor, less than the 950 leftover.

    Sized so the distinction between "floor" and "reclaimed" is observable: at the floor
    the last two items cannot fit; with the leftover reclaimed, every item fits.
    """
    return [
        ContextItem(key="character:mira", text=_sized("c", 200), tier="tierA", priority=1000, pinned=True),
        ContextItem(key="session", text=_sized("s", 100), tier="tierA", priority=999, pinned=True),
        ContextItem(key="beliefs", text=_sized("b", 150), tier="tierA", priority=998),
        ContextItem(key="memories", text=_sized("m", 150), tier="tierA", priority=997),
        ContextItem(key="goals", text=_sized("g", 100), tier="tierA", priority=996),
        ContextItem(key="secrets", text=_sized("x", 100), tier="tierA", priority=995),
    ]


def _full_tier_b_and_c() -> list[ContextItem]:
    """Tiers B and C saturated at exactly their soft caps -- the RAG-heavy turn."""
    return [
        ContextItem(key="rag:b1", text=_sized("1", TIER_B_CAP // 2), tier="tierB", priority=1000),
        ContextItem(key="rag:b2", text=_sized("2", TIER_B_CAP // 2), tier="tierB", priority=999),
        ContextItem(key="rag:c1", text=_sized("3", TIER_C_CAP // 2), tier="tierC", priority=1000),
        ContextItem(key="rag:c2", text=_sized("4", TIER_C_CAP // 2), tier="tierC", priority=999),
    ]


# ── the guard: the reclaim must not touch what tiers B and C need ────────────


def test_tier_a_is_not_expanded_when_tiers_b_and_c_are_full() -> None:
    """The whole point of P7 is that tiers B and C get their share once a corpus exists.

    With B and C saturated, `budget - tier0 - b - c` falls BELOW the fraction floor, so
    the reclaim must select the floor and leave tier A sized exactly as it is today.
    Written before a corpus exists, because with an empty store this bug has no symptom.
    """
    context = MergedContext(items=[*_tier0(), *_hungry_tier_a(), *_full_tier_b_and_c()])
    filled, _ = fill_to_budget(
        context=context, llm_config=_llm_config(), prompt_token_budget=BUDGET
    )
    assert _tier_tokens(filled, "tierA") <= TIER_A_FLOOR


def test_a_saturated_tier_b_keeps_every_item_it_was_given() -> None:
    """The failure this guards: tier A eats the leftover, then tier B has nowhere to go."""
    context = MergedContext(items=[*_tier0(), *_hungry_tier_a(), *_full_tier_b_and_c()])
    filled, _ = fill_to_budget(
        context=context, llm_config=_llm_config(), prompt_token_budget=BUDGET
    )
    surviving = _keys(filled)
    assert "rag:b1" in surviving
    assert "rag:b2" in surviving


def test_the_reclaim_is_still_bounded_by_the_configured_tier_a_ceiling() -> None:
    """`tier_budget_tokens.tier_a` is an absolute ceiling, not a fraction to be exceeded."""
    tiny_ceiling = 300
    context = MergedContext(items=[*_tier0(), *_hungry_tier_a()])
    filled, _ = fill_to_budget(
        context=context,
        llm_config=_llm_config(tier_a_budget=tiny_ceiling),
        prompt_token_budget=BUDGET,
    )
    non_pinned = [i for i in filled.items if i.tier == "tierA" and not i.pinned]
    assert sum(estimate_tokens(i.text) for i in non_pinned) <= tiny_ceiling


# ── the reclaim itself ───────────────────────────────────────────────────────


def test_tier_a_gets_the_whole_budget_when_tiers_b_and_c_are_empty() -> None:
    """Red before the fix: 450 of 1000 tokens reserved for tiers that spend nothing.

    Tier A wants 800. Its floor is 550, so `goals` and `secrets` were dropped. The
    leftover is 950, which fits all of it.
    """
    context = MergedContext(items=[*_tier0(), *_hungry_tier_a()])
    filled, _ = fill_to_budget(
        context=context, llm_config=_llm_config(), prompt_token_budget=BUDGET
    )
    surviving = _keys(filled)
    assert "goals" in surviving
    assert "secrets" in surviving


def test_a_partially_used_tier_b_hands_back_only_what_it_did_not_use() -> None:
    """The reclaim is the actual leftover, not an all-or-nothing switch."""
    small_b = ContextItem(key="rag:b1", text=_sized("1", 100), tier="tierB", priority=1000)
    context = MergedContext(items=[*_tier0(), *_hungry_tier_a(), small_b])
    filled, _ = fill_to_budget(
        context=context, llm_config=_llm_config(), prompt_token_budget=BUDGET
    )
    # leftover = 1000 - 50 (tier0) - 100 (tier B) = 850, above the 550 floor.
    assert _tier_tokens(filled, "tierA") > TIER_A_FLOOR
    assert "rag:b1" in _keys(filled)


def test_tier0_is_charged_against_the_reclaim() -> None:
    """A large tier0 leaves less to hand back; the reclaim must subtract it, not ignore it."""
    fat_tier0 = [
        ContextItem(key="world", text=_sized("w", 300), tier="tier0", priority=100, pinned=True),
    ]
    context = MergedContext(items=[*fat_tier0, *_hungry_tier_a()])
    filled, serialized = fill_to_budget(
        context=context, llm_config=_llm_config(), prompt_token_budget=BUDGET
    )
    assert estimate_tokens(serialized) <= BUDGET


# ── a property that is NOT true, pinned so nobody assumes it ─────────────────


def test_raising_the_tier_a_cap_can_still_drop_an_item_that_previously_fit() -> None:
    """Greedy-with-skip selection is NOT monotone in the cap. Documented, not fixed.

    `_fit_tier_a_pinned_pool` walks items in priority order and SKIPS any that do not fit
    (ISSUE-145 -- stopping instead would truncate the tail). A larger cap can therefore
    admit a high-priority item that was previously skipped, consuming room that a smaller
    lower-priority item behind it was using. Asserted against the helper directly, because
    the reclaim's floor hides the effect at the `fill_to_budget` level.

    This is the mechanism behind the prototype regression recorded in ISSUE-197 ("moved
    captain_sorn from 1 goal to 0"), which that entry attributed to the post-serialization
    trim loop. It is not the trim loop -- it is the fill, and no trim is involved here.
    Replacing greedy selection with something knapsack-shaped is ruled out by D2/DEC-197.
    See ISSUE-209.
    """
    items = [
        ContextItem(key="a", text=_sized("a", 70), tier="tierA", priority=1000),
        ContextItem(key="b", text=_sized("b", 40), tier="tierA", priority=999),
        ContextItem(key="c", text=_sized("c", 30), tier="tierA", priority=998),
    ]
    narrow = {i.key for i in _fit_tier_a_pinned_pool(items=items, budget_tokens=100)}
    wide = {i.key for i in _fit_tier_a_pinned_pool(items=items, budget_tokens=110)}

    assert narrow == {"a", "c"}
    assert wide == {"a", "b"}
    assert "c" not in wide, "c fit at the smaller cap and does not at the larger one"


# ── drop attribution ─────────────────────────────────────────────────────────
#
# Note on fixtures: `_sized` produces non-JSON filler, which is right for the reclaim
# tests above because the greedy fill selects on estimate_tokens alone. It is WRONG for
# anything that depends on the serialized output: serialize_context parses each item and
# rebuilds a fixed skeleton, so filler that is not valid JSON contributes zero bytes. The
# final-trim test below therefore uses real JSON.


def _reasons(report: BudgetFillReport) -> dict[str, str]:
    return {d.key: d.reason for d in report.dropped}


def test_an_item_excluded_by_the_tier_a_soft_cap_is_reported_as_tier_soft_cap() -> None:
    """`tier_soft_cap` has been a declared-but-never-emitted enum member since v1.4.

    Tiers B and C are saturated, so the tier-A cap holds at its 550 floor. Pinned items
    take 300 of it; of the four non-pinned items wanting 500, two cannot fit and are
    excluded by `_fit_tier_a_pinned_pool` before the global fill ever sees them.
    """
    context = MergedContext(items=[*_tier0(), *_hungry_tier_a(), *_full_tier_b_and_c()])
    report = fill_to_budget_with_report(
        context=context, llm_config=_llm_config(), prompt_token_budget=BUDGET
    )
    reasons = _reasons(report)
    assert reasons, "fixture must actually drop something"
    assert reasons.get("memories") == "tier_soft_cap"
    assert reasons.get("secrets") == "tier_soft_cap"


def test_a_compressible_tier_reports_its_own_cap_drops_as_tier_soft_cap() -> None:
    """Tier B drops only when compression cannot get small enough, which is narrow.

    `_field_select_compress` falls back to byte truncation, so it always reaches its
    per-item target -- EXCEPT that MIN_COMPRESSED_CHARS (32 chars, 8 tokens) floors every
    item. Ten items against a 30-token cap therefore still total ~80 after compression,
    and `_fit_compressible_tier` pops the tail until the cap holds. That floor is the only
    way a compressible tier drops anything, which is worth knowing before P7 turns RAG on.
    """
    tiny_budget = 200  # tier B cap = int(200 * 0.30) = 60
    many = [
        ContextItem(key=f"rag:b{i}", text=_sized(str(i), 40), tier="tierB", priority=1000 - i)
        for i in range(10)
    ]
    context = MergedContext(items=[*_tier0(), *many])
    report = fill_to_budget_with_report(
        context=context, llm_config=_llm_config(), prompt_token_budget=tiny_budget
    )
    soft_capped = [d.key for d in report.dropped if d.reason == "tier_soft_cap"]
    assert soft_capped, "compression floor must force at least one tier-B drop"


def test_an_item_dropped_after_serialization_is_reported_as_final_trim() -> None:
    """`final_trim` is the other never-emitted member: post-serialization eviction.

    Uses real JSON because this is the one stage that measures the serialized truth, and a
    budget between the two measurements: the item-token sum is 174, which the estimate-based
    fill accepts at a budget of 200, but the serialized JSON is 217 because the skeleton adds
    ~59 tokens of its own. Only the trim loop can see that.
    """
    crowd = json.dumps([
        {"id": f"npc_{i}", "name": f"Person {i}", "archetype": "villager", "faction": "neutral"}
        for i in range(8)
    ])
    context = MergedContext(items=[
        ContextItem(key="world", text='{"epoch":"war"}', tier="tier0", priority=100, pinned=True),
        ContextItem(key="character:mira", text='{"name":"Mira"}', tier="tierA", priority=1000, pinned=True),
        ContextItem(key="nearby_npcs", text=crowd, tier="tierA", priority=999),
    ])
    report = fill_to_budget_with_report(
        context=context, llm_config=_llm_config(), prompt_token_budget=200
    )
    reasons = _reasons(report)
    assert reasons, "fixture must actually overflow the serialized budget"
    assert reasons.get("nearby_npcs") == "final_trim"


def test_every_dropped_item_is_attributed_exactly_once() -> None:
    """The three stages partition the drops; an item in two buckets is a bookkeeping bug."""
    context = MergedContext(items=[*_tier0(), *_hungry_tier_a(), *_full_tier_b_and_c()])
    report = fill_to_budget_with_report(
        context=context, llm_config=_llm_config(), prompt_token_budget=BUDGET
    )
    keys = [d.key for d in report.dropped]
    assert keys, "fixture must actually drop something"
    assert len(keys) == len(set(keys))


def test_every_assembled_item_either_survives_or_is_attributed() -> None:
    """No item may vanish unaccounted for -- that gap is what the receipt exists to close."""
    context = MergedContext(items=[*_tier0(), *_hungry_tier_a(), *_full_tier_b_and_c()])
    report = fill_to_budget_with_report(
        context=context, llm_config=_llm_config(), prompt_token_budget=BUDGET
    )
    accounted = _keys(report.context) | {d.key for d in report.dropped}
    assert {i.key for i in context.items} == accounted


def test_no_surviving_item_is_reported_as_dropped() -> None:
    context = MergedContext(items=[*_tier0(), *_hungry_tier_a(), *_full_tier_b_and_c()])
    report = fill_to_budget_with_report(
        context=context, llm_config=_llm_config(), prompt_token_budget=BUDGET
    )
    surviving = _keys(report.context)
    assert [d.key for d in report.dropped if d.key in surviving] == []


def test_tier0_is_never_reported_as_dropped() -> None:
    """Tier 0 is pinned by contract; if it ever appears here the contract broke."""
    context = MergedContext(items=[*_tier0(), *_hungry_tier_a(), *_full_tier_b_and_c()])
    report = fill_to_budget_with_report(
        context=context, llm_config=_llm_config(), prompt_token_budget=BUDGET
    )
    assert [d for d in report.dropped if d.tier == "tier0"] == []


def test_the_wrapper_returns_exactly_what_the_report_carries() -> None:
    """fill_to_budget must stay a pure projection of the reporting variant."""
    context = MergedContext(items=[*_tier0(), *_hungry_tier_a(), *_full_tier_b_and_c()])
    cfg = _llm_config()
    filled, serialized = fill_to_budget(
        context=context, llm_config=cfg, prompt_token_budget=BUDGET
    )
    report = fill_to_budget_with_report(
        context=context, llm_config=cfg, prompt_token_budget=BUDGET
    )
    assert _keys(filled) == _keys(report.context)
    assert serialized == report.serialized


@pytest.mark.parametrize("budget", [70, 200, 500, BUDGET, 4000])
def test_the_serialized_output_never_exceeds_the_budget_it_was_given(budget: int) -> None:
    """The reclaim must not break the invariant the whole function exists to hold.

    Exception, by contract: tier0 plus pinned items may exceed it (ISSUE-145), so this
    asserts the loop terminated with nothing droppable left rather than a hard ceiling.
    """
    context = MergedContext(items=[*_tier0(), *_hungry_tier_a(), *_full_tier_b_and_c()])
    filled, serialized = fill_to_budget(
        context=context, llm_config=_llm_config(), prompt_token_budget=budget
    )
    droppable = [i for i in filled.items if i.tier != "tier0" and not i.pinned]
    assert estimate_tokens(serialized) <= budget or not droppable
