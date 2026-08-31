"""
test_context_slot_contract.py - the declaration table is the single source of truth.

Three lists have to agree for a context slot to reach the model, and until this test
existed nothing checked that they did. Every one of the three has already been the cause
of a shipped, silent bug:

  * forget the key in ``NPC_SELF_STATE_KEYS``  -> the item scores proximity 0.0, the score
    of a node at the graph horizon, and ranks below the strangers in the room (ISSUE-163).
  * forget the line in ``context_serializer``  -> the item is produced, ranked, charged to
    the budget and then discarded, costing ~110 tok/turn for nothing (ISSUE-200).
  * forget which field the scorer reads       -> the item is ordered by one field and
    scored on another (ISSUE-206).

So: ``{keys the producers emit} == {keys the table declares}``, and every serialized slot's
path is reachable in the skeleton the serializer builds. The producer side is read out of
the source with ``ast`` rather than by running the pipeline, because a runtime probe only
sees the keys THAT turn happened to produce -- an NPC with no secrets emits no ``secrets``
item, and the check would pass by accident.

Does NOT: execute I/O, touch the graph, call LLM services, or import the running app.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from npc_engine.retrieval.context.context_slots import (
    CONTEXT_SLOTS,
    NPC_SELF_STATE_KEYS,
    POST_SERIALIZATION_SLOTS,
    PRODUCER_FACTORIES,
    PRODUCER_MODULES,
    UNDECLARED_PRODUCER_KEYS,
    serialized_slots,
    slot_for_key,
)

_SRC = pathlib.Path(__file__).resolve().parents[3] / "src"


def _key_literal(node: ast.AST) -> str | None:
    """Return the declared key for a ``ContextItem(key=...)`` argument, or None.

    An f-string key (``f"character:{npc_id}"``) is reduced to its literal prefix, which is
    exactly what the table declares and what the serializer matches on.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        head = node.values[0]
        if isinstance(head, ast.Constant) and isinstance(head.value, str):
            return head.value
        return None
    if isinstance(node, ast.Name):
        return None
    return None


def _producer_keys() -> set[str]:
    """Every key literal passed to ``ContextItem(key=...)`` across the producer modules."""
    found: set[str] = set()
    for rel in PRODUCER_MODULES:
        tree = ast.parse((_SRC / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name not in PRODUCER_FACTORIES:
                continue
            for kw in node.keywords:
                if kw.arg == "key":
                    key = _key_literal(kw.value)
                    if key is not None:
                        found.add(key)
    return found


def test_the_producer_modules_are_the_ones_the_table_names() -> None:
    """A producer module that moved must fail loudly, not silently stop being scanned."""
    for rel in PRODUCER_MODULES:
        assert (_SRC / rel).is_file(), f"PRODUCER_MODULES names a file that does not exist: {rel}"


def test_every_key_a_producer_emits_is_declared_in_the_table() -> None:
    """The bug this closes: an item produced, ranked, budgeted, then silently discarded."""
    undeclared = {
        key for key in _producer_keys()
        if slot_for_key(key) is None and key not in UNDECLARED_PRODUCER_KEYS
    }
    assert undeclared == set(), (
        f"these keys reach the budget but no slot declares them: {sorted(undeclared)}. "
        "Add a row to CONTEXT_SLOTS, or add the key to UNDECLARED_PRODUCER_KEYS with a reason."
    )


def test_every_key_the_table_declares_is_actually_produced() -> None:
    """The mirror bug: a slot the serializer reads that nothing will ever fill."""
    produced = _producer_keys()
    orphaned = {
        slot.key for slot in CONTEXT_SLOTS
        if slot.key not in produced and slot.key not in POST_SERIALIZATION_SLOTS
    }
    assert orphaned == set(), (
        f"these slots have no producer and will be empty in 100% of rows: {sorted(orphaned)}. "
        "Wire a producer or delete the row (and the prompt lines that reference it)."
    )


def test_undeclared_producer_keys_is_an_allowlist_not_an_escape_hatch() -> None:
    """Anything intentionally unserialized must still be named, so it cannot grow quietly."""
    produced = _producer_keys()
    stale = {key for key in UNDECLARED_PRODUCER_KEYS if key not in produced}
    assert stale == set(), f"UNDECLARED_PRODUCER_KEYS names keys nothing produces: {sorted(stale)}"


def test_self_state_keys_are_derived_from_the_table_not_hand_maintained() -> None:
    """ISSUE-163's cause was a second hand-maintained list. There must not be one."""
    expected = tuple(sorted(slot.key for slot in CONTEXT_SLOTS if slot.self_state))
    assert tuple(sorted(NPC_SELF_STATE_KEYS)) == expected


def test_every_serialized_slot_declares_a_skeleton_path() -> None:
    """`default_enabled` without a path is a row that can never do anything."""
    for slot in serialized_slots():
        assert slot.path, f"slot {slot.key!r} is enabled but declares no skeleton path"


def test_no_two_slots_claim_the_same_skeleton_path() -> None:
    """Two rows writing one path is a last-writer-wins bug that no test would otherwise see."""
    seen: dict[str, str] = {}
    for slot in serialized_slots():
        assert slot.path is not None
        clash = seen.get(slot.path)
        assert clash is None, f"{slot.key!r} and {clash!r} both write skeleton path {slot.path!r}"
        seen[slot.path] = slot.key


def test_slot_keys_are_unique() -> None:
    """The table is looked up by key; a duplicate silently shadows."""
    keys = [slot.key for slot in CONTEXT_SLOTS]
    assert len(keys) == len(set(keys)), "duplicate key in CONTEXT_SLOTS"


def test_rag_results_never_land_in_the_authoritative_knowledge_list() -> None:
    """D10, half one: `npc_known_events` is the prompt's anti-hallucination whitelist.

    system_v1.yaml calls it authoritative -- "Do NOT reference any event, person, or fact
    not present in context.npc_known_events". A retrieved node is not an event this NPC
    witnessed, and concatenating the two turns retrieval into manufactured memory.
    """
    rag = slot_for_key("rag:some_node_id")
    assert rag is not None, "rag:* must have its own declared slot"
    events = slot_for_key("event:0:npc_a")
    assert events is not None
    assert rag.path != events.path
    assert rag.path != "npc_known_events"


@pytest.mark.parametrize("key", ["memories", "active_pledges", "beliefs", "goals", "secrets"])
def test_array_payload_slots_name_the_field_the_scorer_reads(key: str) -> None:
    """ISSUE-206: the ordering field and the scored field must be declared in one place."""
    slot = slot_for_key(key)
    assert slot is not None
    assert slot.severity_field is not None, (
        f"{key!r} carries an array of records but does not declare which field scores it"
    )
