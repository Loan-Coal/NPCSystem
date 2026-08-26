"""
test_withheld_slots_cost_nothing.py - a slot the prompt will not carry must not be bought.

ISSUE-200's cost was never the missing serializer lines by themselves. It was that eleven
keys were produced, ranked, and charged against the prompt token budget, and only THEN
discarded -- roughly 110 tokens a turn paid for and never delivered, while tier-A items
that would have reached the model were dropped for want of room.

Declaring those keys in CONTEXT_SLOTS with `default_enabled=False` turned a silent bug into
a written-down decision, but on its own it does not stop the spending. This is the filter
that does: an item whose slot is withheld is dropped before ranking, so it never competes
for budget it cannot use.

The filter is deliberately CENTRAL rather than a check inside each producer. There are four
producer modules and twenty-odd call sites; a per-producer check is exactly the kind of
thing that gets forgotten at the twenty-first, which is how ISSUE-200 happened.

Does NOT: execute I/O, touch the graph, or call LLM services.
"""

from __future__ import annotations

import json

from npc_engine.retrieval.context.context_builder import _drop_withheld_items
from npc_engine.retrieval.context.context_merger import ContextItem
from npc_engine.retrieval.context.context_slots import CONTEXT_SLOTS


def _item(key: str, tier: str = "tierA") -> ContextItem:
    return ContextItem(key=key, text=json.dumps([{"x": 1}]), tier=tier, priority=50)  # type: ignore[arg-type]


def test_a_withheld_slot_is_dropped_before_it_can_be_charged() -> None:
    """`secrets` is declared, has a path, and no prompt rule teaches the model to read it."""
    kept = _drop_withheld_items([_item("secrets"), _item("beliefs")])
    assert [i.key for i in kept] == ["beliefs"]


def test_every_enabled_slot_survives_the_filter() -> None:
    """The filter must remove only what the table withholds, nothing else."""
    enabled = [slot for slot in CONTEXT_SLOTS if slot.default_enabled]
    items = [_item(slot.key + "x" if slot.key.endswith(":") else slot.key) for slot in enabled]
    assert len(_drop_withheld_items(items)) == len(items)


def test_an_undeclared_key_survives_rather_than_being_swallowed() -> None:
    """Fail open. A key the table does not know is a contract-test failure, not a silent drop.

    Dropping it here would hide exactly the defect `test_context_slot_contract` exists to
    surface, and would do it in production rather than in CI.
    """
    assert [i.key for i in _drop_withheld_items([_item("a_key_nobody_declared")])] == [
        "a_key_nobody_declared"
    ]


def test_a_withheld_prefix_family_is_dropped_by_prefix() -> None:
    """`second_hop:` is an indexed family; every member must go, not just an exact match."""
    items = [_item("second_hop:0:npc_a"), _item("second_hop:1:npc_a"), _item("event:0:npc_a")]
    assert [i.key for i in _drop_withheld_items(items)] == ["event:0:npc_a"]


def test_the_filter_preserves_order() -> None:
    """Ranking is stable on ties, so reordering here would silently reorder the prompt."""
    items = [_item("beliefs"), _item("secrets"), _item("goals"), _item("traits"), _item("memories")]
    assert [i.key for i in _drop_withheld_items(items)] == ["beliefs", "goals", "memories"]


def test_an_empty_list_stays_empty() -> None:
    assert _drop_withheld_items([]) == []
