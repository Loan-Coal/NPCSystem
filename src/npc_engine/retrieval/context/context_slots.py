"""
Module: context_slots
Layer: retrieval
Purpose: THE declaration table -- every context key the pipeline can put in front of the
         model, declared once, with everything the producer, the scorer and the serializer
         each need to know about it.
Does NOT: produce items, score them, serialize them, or read configuration. It is data.
Dependencies injected: none -- this module is data and pure functions.
Used by: context_serializer (generates the skeleton from it), context_scoring (derives
         NPC_SELF_STATE_KEYS and the severity-field mapping from it), and
         tests/unit/retrieval/test_context_slot_contract.py (enforces it).

Why this file exists
--------------------
Getting one fact about an NPC in front of the model takes three edits in three files, and
missing any one of them fails SILENTLY. All three have shipped:

  ISSUE-163  forgot the key in NPC_SELF_STATE_KEYS, so an NPC's own beliefs scored
             proximity 0.0 -- the score of a node at the graph horizon -- and ranked below
             the strangers standing in the room. Under a 281-token cap that is the
             difference between reaching the prompt and being dropped.
  ISSUE-200  forgot the line in context_serializer, so eleven keys were produced, ranked,
             charged to the budget and then thrown away at the last step: ~110 tok/turn
             bought and never delivered.
  ISSUE-206  ordered a payload by one field and scored it on another, so the "most
             important" record the scorer sees is not the one the producer chose.

Adding a field is now: a reader, ONE row here, and one prompt rule. Three edits, and the
contract test fails loudly if you make two of them.

Reading the table
-----------------
Rows are applied to the skeleton IN ORDER. That matters in exactly one place and it is
deliberate: ``character:`` writes the whole ``npc.profile`` object and ``location:`` then
writes ``npc.profile.current_location`` into it, so ``character:`` must come first.
Nothing else in the table depends on order.
"""

from __future__ import annotations

from npc_engine.schema.context_slot_models import ContextSlot

__all__ = [
    "CONTEXT_SLOTS",
    "NPC_SELF_STATE_KEYS",
    "POST_SERIALIZATION_SLOTS",
    "PRODUCER_FACTORIES",
    "PRODUCER_MODULES",
    "SELF_STATE_PROXIMITY_HOPS",
    "UNDECLARED_PRODUCER_KEYS",
    "serialized_slots",
    "severity_field_for_key",
    "slot_for_key",
]

_PREFIX_SHAPES = ("prefix_first", "prefix_collect")

PRODUCER_FACTORIES: tuple[str, ...] = ("ContextItem", "_pinned_tier0_item")
"""Every call that mints a context item, by callee name.

``ContextItem`` is the type; ``_pinned_tier0_item`` is the tier-0 wrapper around it, and
scanning only for the former missed ``world``, ``emotion`` and ``system_state`` entirely.
A new wrapper that is not named here makes the contract test fail, not pass.
"""

PRODUCER_MODULES: tuple[str, ...] = (
    "npc_engine/retrieval/context/context_builder.py",
    "npc_engine/retrieval/context/context_graph_readers.py",
    "npc_engine/retrieval/graph_rag/subgraph_retriever.py",
    "npc_engine/engines/dialogue/negotiation_context.py",
)
"""Every module that constructs a ContextItem, relative to ``src/``.

The contract test scans these with ``ast`` rather than running the pipeline: a runtime
probe only sees the keys THAT turn produced, so an NPC with no secrets emits no ``secrets``
item and the check would pass by accident. Naming a file that has moved fails the test.
"""

POST_SERIALIZATION_SLOTS: frozenset[str] = frozenset({"active_negotiation"})
"""Skeleton keys merged in AFTER serialize_context, by a module outside the pipeline.

``engines/dialogue/negotiation_context.inject_active_negotiation`` merges the live
negotiation summary straight from the session object, so this key never enters
MergedContext and is never charged to the budget. It is named here rather than left
undocumented, because a skeleton key the table does not declare is otherwise
indistinguishable from the ISSUE-200 bug.
"""

UNDECLARED_PRODUCER_KEYS: frozenset[str] = frozenset()
"""Keys a producer emits that the table intentionally does not declare.

Empty, and it should stay that way. It exists so that a deliberate exception has to be
written down next to a reason instead of silently widening the contract test.
"""

SELF_STATE_PROXIMITY_HOPS = 0
"""An NPC's own state is zero hops from the NPC, the same as its character node."""


# fmt: off
CONTEXT_SLOTS: tuple[ContextSlot, ...] = (
    # --- tier 0: pinned, never dropped, never compressed -------------------------------
    ContextSlot(key="world", tier="tier0", priority=100, pinned=True,
                path="world", shape="object",
                self_state=False, default_enabled=True, severity_field=None),
    # system_state was pinned at priority 97 and then discarded at serialization: a slot
    # the budget always paid for and the model could never see. system_state_v1.yaml
    # Rule 17 has been teaching the model to read it the whole time.
    ContextSlot(key="system_state", tier="tier0", priority=97, pinned=True,
                path="system_state", shape="object",
                self_state=False, default_enabled=True, severity_field=None),
    ContextSlot(key="emotion", tier="tier0", priority=95, pinned=True,
                path="npc.emotion", shape="object",
                self_state=False, default_enabled=True, severity_field=None),

    # --- tier A: the NPC, the player, and the room -------------------------------------
    # MUST precede location: -- it writes the object that location: writes a field into.
    ContextSlot(key="character:", tier="tierA", priority=100, pinned=False,
                path="npc.profile", shape="prefix_first",
                self_state=False, default_enabled=True, severity_field=None),
    ContextSlot(key="session", tier="tierA", priority=99, pinned=True,
                path="recent_session_turns", shape="list",
                self_state=False, default_enabled=True, severity_field=None),
    # Two producers emit this key -- subgraph_retriever at 95 and context_builder at 88.
    # merge_context dedups; the higher priority is the one that survives (ISSUE-070).
    ContextSlot(key="relation:player", tier="tierA", priority=95, pinned=False,
                path="player_relation", shape="object",
                self_state=False, default_enabled=True, severity_field=None),
    # The location node is large and contributes exactly one string to the prompt.
    ContextSlot(key="location:", tier="tierA", priority=92, pinned=False,
                path="npc.profile.current_location", shape="prefix_first",
                extract_field="name",
                self_state=False, default_enabled=True, severity_field=None),
    ContextSlot(key="nearby_npcs", tier="tierA", priority=91, pinned=False,
                path="nearby_npcs", shape="list",
                self_state=False, default_enabled=True, severity_field=None),
    ContextSlot(key="player_memories", tier="tierA", priority=91, pinned=False,
                path="npc.player_memories", shape="list",
                self_state=True, default_enabled=True, severity_field="emotional_charge"),
    ContextSlot(key="memories", tier="tierA", priority=90, pinned=False,
                path="npc.memories", shape="list",
                self_state=True, default_enabled=True, severity_field="emotional_charge"),
    # priority is 89 - i: the base, decremented per event index by the producer.
    ContextSlot(key="event:", tier="tierA", priority=89, pinned=False,
                path="npc_known_events", shape="prefix_collect",
                self_state=False, default_enabled=True, severity_field="severity"),
    # Pinned at 89 and never serialized. system_v1.yaml Rule 11 tells the model to set
    # action.target_id to "the quest_id" -- and never gave it one.
    ContextSlot(key="active_quest", tier="tierA", priority=89, pinned=True,
                path="active_quest", shape="object",
                self_state=False, default_enabled=True, severity_field=None),
    ContextSlot(key="beliefs", tier="tierA", priority=88, pinned=False,
                path="npc.beliefs", shape="list",
                self_state=True, default_enabled=True, severity_field="confidence"),
    ContextSlot(key="goals", tier="tierA", priority=87, pinned=False,
                path="npc.goals", shape="list",
                self_state=True, default_enabled=True, severity_field="urgency"),
    ContextSlot(key="reputation", tier="tierA", priority=85, pinned=False,
                path="player_reputation", shape="list",
                self_state=False, default_enabled=True, severity_field=None),
    ContextSlot(key="propagated_reputation", tier="tierA", priority=84, pinned=False,
                path="propagated_reputation", shape="list",
                self_state=False, default_enabled=True, severity_field="reputation_delta"),

    # --- tier A, declared but withheld: no prompt rule teaches the model to read them ---
    # These are the ISSUE-200 orphans. They are produced, ranked and charged to the budget
    # today and discarded at serialization; declaring them with default_enabled=False makes
    # that a DECISION with a path already written down, so turning one on is one flag.
    ContextSlot(key="owned_items", tier="tierA", priority=86, pinned=False,
                path="npc.owned_items", shape="list",
                self_state=True, default_enabled=False, severity_field=None),
    ContextSlot(key="secrets", tier="tierA", priority=84, pinned=False,
                path="npc.secrets", shape="list",
                self_state=True, default_enabled=False, severity_field="severity"),
    ContextSlot(key="traits", tier="tierA", priority=83, pinned=False,
                path="npc.traits", shape="list",
                self_state=True, default_enabled=False, severity_field="intensity"),
    ContextSlot(key="obligations", tier="tierA", priority=83, pinned=False,
                path="npc.obligations", shape="list",
                self_state=True, default_enabled=False, severity_field=None),
    ContextSlot(key="group_memberships", tier="tierA", priority=82, pinned=False,
                path="npc.group_memberships", shape="list",
                self_state=True, default_enabled=False, severity_field="cohesion"),
    ContextSlot(key="believed_rumors", tier="tierA", priority=81, pinned=False,
                path="npc.believed_rumors", shape="list",
                self_state=True, default_enabled=False, severity_field="confidence"),
    ContextSlot(key="active_pledges", tier="tierA", priority=79, pinned=False,
                path="npc.active_pledges", shape="list",
                self_state=True, default_enabled=False, severity_field="severity"),
    # priority is 74 - idx. Second-hand events are NOT npc_known_events: the prompt calls
    # that list authoritative, and these reached the NPC through someone else.
    ContextSlot(key="second_hop:", tier="tierA", priority=74, pinned=False,
                path="npc_secondhand_events", shape="prefix_collect",
                self_state=False, default_enabled=False, severity_field="severity"),

    # --- tier B / C: retrieval ---------------------------------------------------------
    ContextSlot(key="top_need", tier="tierB", priority=60, pinned=False,
                path="npc.top_need", shape="object_or_null",
                self_state=True, default_enabled=True, severity_field="urgency"),
    # D10, half one. npc_known_events is the prompt's anti-hallucination whitelist --
    # "Do NOT reference any event, person, or fact not present in context.npc_known_events".
    # RAG hits were concatenated INTO that list, which turns a retrieved node into an event
    # the NPC swears it witnessed. Its own slot, with its own prompt rule (P8).
    # priority is max(1, 60 - index).
    ContextSlot(key="rag:", tier="tierB", priority=60, pinned=False,
                path="retrieved_context", shape="prefix_collect",
                self_state=False, default_enabled=True, severity_field="severity"),
)
# fmt: on
"""Every context key the pipeline can put in front of the model. Order is significant."""


_BY_KEY: dict[str, ContextSlot] = {slot.key: slot for slot in CONTEXT_SLOTS}


def slot_for_key(item_key: str) -> ContextSlot | None:
    """Return the slot a merged-context item key belongs to, or None if undeclared.

    Exact matches win over prefix matches, so a future exact key that happens to share a
    prefix cannot be swallowed by the family it looks like.

    Args:
        item_key: The key carried by a ContextItem.
    Returns:
        The declaring ContextSlot, or None when no row claims the key.
    """
    exact = _BY_KEY.get(item_key)
    if exact is not None and exact.shape not in _PREFIX_SHAPES:
        return exact
    for slot in CONTEXT_SLOTS:
        if slot.matches(item_key):
            return slot
    return None


def serialized_slots() -> tuple[ContextSlot, ...]:
    """Return, in table order, the slots the shipped serializer emits."""
    return tuple(slot for slot in CONTEXT_SLOTS if slot.default_enabled)


def severity_field_for_key(item_key: str) -> str | None:
    """Return the payload field the relevance scorer should read for this key.

    ISSUE-206: an array payload is scored on one representative record, so the field the
    producer ORDERS BY and the field the scorer READS must be the same one, or the ranking
    reflects a choice nobody made.

    Args:
        item_key: The key carried by a ContextItem.
    Returns:
        The declared severity-family field name, or None to fall back to the generic chain.
    """
    slot = slot_for_key(item_key)
    return slot.severity_field if slot is not None else None


NPC_SELF_STATE_KEYS: tuple[str, ...] = tuple(
    slot.key for slot in CONTEXT_SLOTS if slot.self_state
)
"""Context keys carrying state that hangs directly off the NPC's own Character node.

DERIVED from the table, deliberately. This was a hand-maintained tuple, and a key missing
from it fell through to the ``max_proximity_hops`` default -- proximity 0.0, the score of a
node at the graph horizon -- so an NPC's own beliefs and memories ranked below the
strangers standing in the room with it (ISSUE-163).
"""
