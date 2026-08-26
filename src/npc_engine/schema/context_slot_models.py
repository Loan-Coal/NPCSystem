"""
Module: context_slot_models
Layer: schema
Purpose: The row type for the context-slot declaration table -- one frozen record per key
         the retrieval pipeline can put in front of the model.
Does NOT: hold the table itself (that is retrieval/context/context_slots.py), read
          configuration, or serialize anything.
Dependencies injected: none -- this module is data and pure functions.
Used by: retrieval.context.context_slots, retrieval.context.context_serializer,
         retrieval.context.context_scoring, and the slot contract test.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = ["SLOT_SHAPES", "ContextSlot", "SlotShape", "TierName"]

TierName = Literal["tier0", "tierA", "tierB", "tierC"]
"""The four assembly tiers, in the spelling the producers and the budget enforcer use."""

SlotShape = Literal["object", "list", "object_or_null", "prefix_first", "prefix_collect"]
"""How one slot's payload is read out of the merged context and written to the skeleton.

``object``          exact key; payload is a mapping. Empty default ``{}``.
``list``            exact key; payload is an array. Empty default ``[]``.
``object_or_null``  exact key; payload is a mapping, and its ABSENCE is meaningful, so the
                    empty default is ``null`` rather than ``{}``.
``prefix_first``    ``key`` is a prefix; the FIRST matching item wins. Empty default ``{}``,
                    or ``null`` when ``extract_field`` is set (a missing scalar is null,
                    not an empty object).
``prefix_collect``  ``key`` is a prefix; every matching item's payload is collected, in
                    merged-context order. Empty default ``[]``.
"""

SLOT_SHAPES: frozenset[str] = frozenset(
    {"object", "list", "object_or_null", "prefix_first", "prefix_collect"}
)
"""Runtime mirror of SlotShape, for exhaustiveness checks the type system cannot make."""

_PREFIX_SHAPES: frozenset[str] = frozenset({"prefix_first", "prefix_collect"})


class ContextSlot(BaseModel):
    """One declared context slot: what produces it, how it scores, and where it lands.

    A slot is the unit that has to be got right in three places at once for a fact about an
    NPC to reach the model -- the producer, the relevance scorer, and the serializer. Each
    of those three has already silently dropped a slot on the floor in production
    (ISSUE-163, ISSUE-200, ISSUE-206). This row is the single place they are reconciled,
    and `tests/unit/retrieval/test_context_slot_contract.py` is what reconciles them.

    Attributes:
        key: The exact context-item key, or its literal prefix for the prefix shapes.
        tier: Assembly tier the producer emits this item into.
        priority: The producer's declared priority. Documentation of intent -- the producer
            remains the source of truth, and for indexed families (``event:``,
            ``second_hop:``, ``rag:``) this is the BASE before the per-index decrement.
        pinned: Whether the budget enforcer may never drop this item.
        path: Dotted path in the serialized skeleton, e.g. ``npc.beliefs``. ``None`` means
            the slot is deliberately not serialized; `default_enabled` must then be False.
        shape: How the payload is read and what its empty default is. See SlotShape.
        extract_field: When set, the slot writes THIS FIELD of the matched payload rather
            than the payload itself. Exists for ``location:``, whose 2,000-token location
            node contributes exactly one string -- the name -- to ``npc.profile``.
        self_state: True when the payload hangs directly off the NPC's own Character node,
            which makes it ZERO hops away. NPC_SELF_STATE_KEYS is derived from this field;
            it used to be a second hand-maintained tuple, and forgetting a key there scored
            an NPC's own beliefs at the graph horizon (ISSUE-163).
        default_enabled: Whether the shipped serializer emits this slot. False means
            produced, ranked and charged to the budget but deliberately withheld from the
            prompt -- normally because no prompt rule teaches the model to read it.
            P8 turns this into an A/B knob via RetrievalProfile.disabled_slots.
        severity_field: The field ``_extract_severity_score`` should read for this slot.
            Array payloads are scored on one representative record, so the field the
            producer ORDERS BY and the field the scorer READS have to be the same one or
            the ranking is measuring something nobody chose (ISSUE-206).
    """

    key: str = Field(min_length=1)
    tier: TierName
    priority: int = Field(ge=0, le=1000)
    pinned: bool
    path: str | None
    shape: SlotShape
    extract_field: str | None = None
    self_state: bool
    default_enabled: bool
    severity_field: str | None = None

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    @model_validator(mode="after")
    def _validate_row_is_coherent(self) -> "ContextSlot":
        """Reject rows whose columns contradict each other.

        These are the shapes of mistake the table exists to make impossible, so they are
        caught at import time rather than as a mysteriously empty prompt slot.

        Raises:
            ValueError: When the row is internally inconsistent.
        """
        if self.default_enabled and self.path is None:
            raise ValueError(f"slot {self.key!r} is enabled but has no skeleton path")
        if self.extract_field is not None and self.shape not in _PREFIX_SHAPES:
            raise ValueError(f"slot {self.key!r} sets extract_field on a non-prefix shape")
        if self.shape in _PREFIX_SHAPES and not self.key.endswith(":"):
            raise ValueError(f"slot {self.key!r} has a prefix shape but is not a ':' prefix")
        if self.shape not in _PREFIX_SHAPES and self.key.endswith(":"):
            raise ValueError(f"slot {self.key!r} looks like a prefix but has an exact shape")
        return self

    def matches(self, item_key: str) -> bool:
        """Return whether a merged-context item key belongs to this slot.

        Args:
            item_key: The key carried by a ContextItem.
        Returns:
            True for an exact match, or for a prefix match on the prefix shapes.
        """
        if self.shape in _PREFIX_SHAPES:
            return item_key.startswith(self.key)
        return item_key == self.key
