"""
Module: context_serializer
Layer: retrieval
Purpose: Turn a merged context into the fixed-schema JSON object the prompt injects, by
         walking the declaration table rather than by 114 hand-written lines.
Does NOT: enforce the token budget, merge tiers, rank, or read configuration.
Dependencies injected: none -- the table is imported data, the context is passed in.
Used by: context_builder_helpers, context_budget_enforcer, and the debug retrieval route.

What changed and why
--------------------
This module used to name every key twice: once to pull it out of the merged context and
once to place it in the skeleton. Eleven produced keys were named in neither, so they were
ranked, charged to the prompt budget and then dropped here without a trace (ISSUE-200,
~110 tok/turn). ``retrieval/context/context_slots.py`` now declares each key once and this
file is a generic walk over that declaration, so a slot cannot be produced and forgotten:
the contract test fails first.

Two behaviours are load-bearing and easy to undo by accident:

**Every enabled slot is emitted every turn.** ``player_memories`` used to appear only when
the NPC had some, so the prompt's SCHEMA varied between turns -- and between the arms of an
A/B run, where it reads as a treatment effect. An empty slot is emitted with its declared
empty default instead.

**Rows are applied in table order.** ``character:`` writes ``npc.profile`` and ``location:``
then writes ``npc.profile.current_location`` into that same object. Nothing else depends on
order, and the table says so where it matters.
"""

from __future__ import annotations

import json
from typing import Any

from npc_engine.schema.context_slot_models import ContextSlot

from .context_merger import MergedContext
from .context_slots import serialized_slots
from .context_utils import serialize_json

__all__ = ["serialize_context"]

_EMPTY_DEFAULTS: dict[str, Any] = {
    "object": {},
    "list": [],
    "object_or_null": None,
    "prefix_first": {},
    "prefix_collect": [],
}
"""What a slot contributes when nothing produced it this turn. See SlotShape."""

_EXPECTED_TYPE: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "list": list,
    "object_or_null": dict,
    "prefix_first": dict,
}
"""The JSON type each shape requires. A payload of any other type falls back to the default.

Graph readers are a system boundary: a reader that starts returning a list where an object
is expected must produce an empty slot, not a prompt containing a stray array.
"""


def _safe_parse(text: str) -> Any:
    """Parse an item's serialized payload, returning the raw text when it is not JSON."""
    try:
        return json.loads(text)
    except ValueError:
        return text


def _empty_for(slot: ContextSlot) -> Any:
    """Return the value a slot contributes when no item produced it."""
    if slot.extract_field is not None:
        return None
    return _EMPTY_DEFAULTS[slot.shape]


def _collected(slot: ContextSlot, context: MergedContext) -> list[Any]:
    """Return every matching item's payload, in merged-context order."""
    return [_safe_parse(item.text) for item in context.items if slot.matches(item.key)]


def _value_for(slot: ContextSlot, context: MergedContext) -> Any:
    """Read one slot's value out of the merged context, or its empty default.

    Args:
        slot: The declared slot to read.
        context: The merged, budget-enforced context.
    Returns:
        The slot's payload coerced to its declared shape, or the shape's empty default.
    """
    if slot.shape == "prefix_collect":
        return _collected(slot, context)
    payload = next(
        (_safe_parse(item.text) for item in context.items if slot.matches(item.key)),
        None,
    )
    if payload is None or not isinstance(payload, _EXPECTED_TYPE[slot.shape]):
        return _empty_for(slot)
    if slot.extract_field is not None:
        return payload.get(slot.extract_field)
    return payload


def _place(skeleton: dict[str, Any], path: str, value: Any) -> None:
    """Write a value at a dotted skeleton path, creating intermediate objects as needed.

    An intermediate that is not an object is replaced rather than merged into: the only
    such path is ``npc.profile.current_location``, whose parent is written first by an
    earlier row, and a non-object there would mean that row got a malformed payload.
    """
    parts = path.split(".")
    node = skeleton
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


def serialize_context(context: MergedContext) -> str:
    """Serialize a merged context into the fixed-schema JSON string the prompt injects.

    The schema is generated from ``context_slots.CONTEXT_SLOTS``: every slot with
    ``default_enabled`` contributes its declared path unconditionally, so the object's
    SHAPE is the same on every turn for every NPC and only its contents vary. A slot with
    ``default_enabled=False`` is absent entirely rather than present-and-empty -- an empty
    key would assert that the NPC has none of that thing, which is a different claim from
    the engine declining to say.

    Args:
        context: Merged and budget-enforced context to serialize.
    Returns:
        Compact JSON string with sorted keys, suitable for prompt injection.
    """
    skeleton: dict[str, Any] = {}
    for slot in serialized_slots():
        assert slot.path is not None  # guaranteed by ContextSlot's validator
        _place(skeleton, slot.path, _value_for(slot, context))
    return serialize_json(skeleton, compact=True)
