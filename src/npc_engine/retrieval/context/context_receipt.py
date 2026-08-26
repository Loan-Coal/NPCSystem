"""
Module: context_receipt
Layer: retrieval
Purpose: The receipt of one context assembly — which items actually REACHED the model,
         what each tier spent, and whether the prompt budget trimmed anything. Retrieval
         precision measured over what the retriever RANKED and precision measured over
         what SURVIVED the budget are different numbers; without this record only the
         first is observable.
Dependencies: pydantic; context_merger (MergedContext), context_utils (estimate_tokens)
Used by: context_builder (produces one per assembly), engines.dialogue (carries it on the
         response), evals/generate_runner (stores it on every transcript record)

Does NOT: retrieve, rank, serialize, or mutate context — it only describes an assembly
that already happened. Lives in its own module because context_builder.py is past the
300-line cap and must not grow.

Dependencies injected: None — every input is passed per call; nothing is read from
module-level state, Settings, or the graph.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field

from .context_merger import ContextTier, MergedContext
from .context_metrics import ContextDropReason
from .context_utils import estimate_tokens

__all__ = [
    "REPORTED_TIERS",
    "BudgetFillReport",
    "ContextReceipt",
    "DroppedItem",
    "TierSpend",
    "build_context_receipt",
]

REPORTED_TIERS: tuple[ContextTier, ...] = ("tier0", "tierA", "tierB", "tierC")
"""Every tier is reported, including empty ones.

An omitted tier reads as "not measured"; a tier reported at zero is a measurement. The
distinction matters because "tier B got no budget" is precisely the finding this record
exists to surface.
"""


class DroppedItem(BaseModel):
    """One assembled item that did not reach the model, and which stage removed it.

    Attributes:
        key: The context item's key.
        tier: The tier it was assembled into.
        reason: Which stage of budget enforcement removed it.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    tier: ContextTier
    reason: ContextDropReason


class BudgetFillReport(BaseModel):
    """The full result of one budget-enforcement pass, drops included.

    `fill_to_budget` returns only the surviving context and its serialization, which is
    all every caller needed before drop attribution existed. This is the same pass with
    the evidence attached, so the two never diverge.

    Attributes:
        context: The context that survived enforcement.
        serialized: That context's serialized prompt text.
        dropped: Every assembled item that did not survive, attributed to one stage.
    """

    model_config = ConfigDict(frozen=True)

    context: MergedContext
    serialized: str
    dropped: tuple[DroppedItem, ...] = ()


class TierSpend(BaseModel):
    """What one context tier actually spent in the assembled prompt.

    Attributes:
        tier: The context tier this row describes.
        items: Number of items from this tier that reached the model.
        tokens: Estimated token count those items occupied.
    """

    model_config = ConfigDict(frozen=True)

    tier: ContextTier
    items: int
    tokens: int


class ContextReceipt(BaseModel):
    """Evidence of what one dialogue turn's context assembly actually produced.

    Frozen: a receipt describes a completed assembly, so it must not be editable after
    the fact by anything that later reads it.

    Attributes:
        retrieval_profile: Resolved profile NAME this turn ran under — the A/B arm.
        item_keys: Keys of the context items that reached the model, in assembly order.
        dropped: Every assembled item that did not survive, each attributed to the stage
            that removed it. The gap between this and item_keys is the whole point.
        tier_spend: Per-tier item and token spend, one row per REPORTED_TIERS entry.
        total_tokens: Estimated tokens across every tier that reached the model.
        prompt_token_budget: The budget the assembly was held to, recorded so a receipt
            read later is interpretable without the Settings that produced it.
        budget_trimmed: Whether any assembled item failed to reach the model.
    """

    model_config = ConfigDict(frozen=True)

    retrieval_profile: str
    item_keys: tuple[str, ...] = Field(default=())
    dropped: tuple[DroppedItem, ...] = Field(default=())
    tier_spend: tuple[TierSpend, ...] = Field(default=())
    total_tokens: int = 0
    prompt_token_budget: int = 0
    budget_trimmed: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dropped_keys(self) -> tuple[str, ...]:
        """The dropped keys alone, as this receipt reported them before P4.

        Computed rather than stored so it cannot drift from `dropped`. It stays in the
        serialized payload, which is what keeps `evals/context_receipt_record.py` and the
        transcripts already on disk readable without a coordinated change.
        """
        return tuple(item.key for item in self.dropped)


def _tier_spend(post_budget: MergedContext) -> tuple[TierSpend, ...]:
    """Sum items and estimated tokens per tier over the context that reached the model."""
    rows: list[TierSpend] = []
    for tier in REPORTED_TIERS:
        items = [item for item in post_budget.items if item.tier == tier]
        rows.append(
            TierSpend(
                tier=tier,
                items=len(items),
                tokens=sum(estimate_tokens(item.text) for item in items),
            )
        )
    return tuple(rows)


def build_context_receipt(
    *,
    profile_name: str,
    post_budget: MergedContext,
    dropped: tuple[DroppedItem, ...],
    prompt_token_budget: int,
) -> ContextReceipt:
    """Describe one completed context assembly.

    Takes the drops as data rather than deriving them from a pre/post set difference: the
    enforcer knows which STAGE removed each item, and that distinction is lost the moment
    it is recomputed from two contexts.

    Args:
        profile_name: Resolved retrieval-profile name for this turn.
        post_budget: The context that actually reached the model.
        dropped: Attributed drops, as reported by fill_to_budget_with_report.
        prompt_token_budget: Budget the enforcement was held to.
    Returns:
        A frozen ContextReceipt. Never raises: a receipt that fails to be produced would
        make the turn it describes unattributable, which is worse than a coarse receipt.
    """
    spend = _tier_spend(post_budget)
    return ContextReceipt(
        retrieval_profile=profile_name,
        item_keys=tuple(item.key for item in post_budget.items),
        dropped=dropped,
        tier_spend=spend,
        total_tokens=sum(row.tokens for row in spend),
        prompt_token_budget=prompt_token_budget,
        budget_trimmed=bool(dropped),
    )
