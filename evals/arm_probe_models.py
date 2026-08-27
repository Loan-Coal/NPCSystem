"""
Module: arm_probe_models
Layer: evals (eval harness — not part of src/)
Purpose: Frozen Pydantic v2 models for the P9 arm probe — one gate's verdict, and one
         arm's observed retrieval for one case.
Does NOT: call the engine, run pytest, or decide anything.
Dependencies injected: none — pure data.
Used by: evals.arm_probe_gates, evals.arm_probe.

A gate that returns a bare bool cannot say WHY it failed, and a gate that fails silently
on an empty input is worse than no gate. Every verdict here therefore carries its own
evidence, and `GateResult.detail` is printed whether the gate passed or failed.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ArmObservation", "GateResult", "TierRow"]


class TierRow(BaseModel):
    """One tier's item and token spend, as the context receipt reported it."""

    model_config = ConfigDict(frozen=True)

    tier: str
    items: int
    tokens: int


class ArmObservation(BaseModel):
    """What one arm retrieved for one case, read from the debug route's receipt.

    Attributes:
        arm: Resolved retrieval-profile name — the arm's own claim about itself.
        npc_id: NPC the context was assembled for.
        query: Player message used as the retrieval signal.
        item_keys: Keys of the items that reached the model, in assembly order.
        tier_spend: Per-tier item and token spend.
        total_tokens: Estimated tokens across every tier.
    """

    model_config = ConfigDict(frozen=True)

    arm: str
    npc_id: str
    query: str
    item_keys: tuple[str, ...] = ()
    tier_spend: tuple[TierRow, ...] = ()
    total_tokens: int = 0

    def tier_items(self, tier: str) -> int:
        """Return the item count for one tier, or 0 when the tier was not reported."""
        for row in self.tier_spend:
            if row.tier == tier:
                return row.items
        return 0

    def tier_tokens(self, tier: str) -> int:
        """Return the token spend for one tier, or 0 when the tier was not reported."""
        for row in self.tier_spend:
            if row.tier == tier:
                return row.tokens
        return 0

    def count_keys(self, prefix: str) -> int:
        """Count item keys carrying one slot prefix, e.g. 'rag:' or 'event:'.

        This is the SUPPLY a top-k knob is bounded by. An arm that raises a limit above
        the number of items that exist cannot change anything, and without this the
        failure reads as "the arm did nothing" rather than "there was nothing to take".
        """
        return sum(1 for key in self.item_keys if key.startswith(prefix))


class GateResult(BaseModel):
    """One gate's verdict and the evidence behind it.

    Attributes:
        number: Gate ordinal. The order is load-bearing — each gate is meaningless until
            the previous one holds, so the runner stops at the first failure.
        name: Short gate name.
        passed: Whether the gate held.
        detail: Lines of evidence, printed on pass AND on failure. A gate whose output
            is only visible when it fails cannot be checked for having run at all.
    """

    model_config = ConfigDict(frozen=True)

    number: int
    name: str
    passed: bool
    detail: tuple[str, ...] = Field(default=())
