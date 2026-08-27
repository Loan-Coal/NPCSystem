"""
Module: retrieval_profile_models
Layer: schema
Purpose: The named retrieval configuration that a dialogue turn is generated under —
         the A/B switch for context experiments. A profile bundles the retrieval-tier
         knobs (relevance weights, the three top-k call sites, cross-encoder, skip_rag)
         so an arm can be selected by NAME rather than by editing code and rebuilding.
Dependencies: pydantic; npc_engine.utils.errors (same rank, permitted)
Used by: retrieval/context (profile-driven assembly), engines/dialogue (request field),
         api routes (4xx on an unknown name), evals/run_config (records the resolved name)

Does NOT: read Settings or any file, perform retrieval, or touch the graph.

Dependencies injected: None — defaults are passed in by the caller, matching the sibling
convention in config_prompt_window.py, so this module stays pure and testable.

Serving-tier properties (OLLAMA_CONTEXT_LENGTH, PROMPT_TOKEN_BUDGET) are deliberately NOT
here. They are fixed at Settings construction, changing num_ctx forces a KV-cache realloc,
and they belong to model serving rather than retrieval — mixing the two tiers in one config
object is how a profile stops being reasonable about.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from npc_engine.utils.errors import RetrievalProfileNotFoundError

__all__ = [
    "ALL_CONTEXT_TIERS",
    "DEFAULT_RAG_SLOT_CAP_TOKENS",
    "DEFAULT_RETRIEVAL_PROFILE_NAME",
    "MAX_TOP_K",
    "RAG_SLOT_KEY",
    "RetrievalProfile",
    "build_default_profile",
    "resolve_retrieval_profile",
]

DEFAULT_RETRIEVAL_PROFILE_NAME: str = "default"
"""The profile production runs under when no override is supplied.

Always resolvable without being declared in YAML: requiring a declaration would make the
engine unbootable on a config that omits it, for no benefit.
"""

MAX_TOP_K: int = 50
"""Upper bound on any top-k field. Not a tuning limit — a guard against a mistyped YAML
value silently requesting a retrieval sweep large enough to blow the token budget."""

ContextTierName = Literal["tier0", "tierA", "tierB", "tierC"]
"""The four assembly tiers, in the spelling the producers and the budget enforcer use."""

ALL_CONTEXT_TIERS: frozenset[str] = frozenset({"tier0", "tierA", "tierB", "tierC"})
"""Every tier, which is what an unspecified profile enables — the default path unchanged."""

RAG_SLOT_KEY: str = "rag:"
"""The declaration-table key for retrieved tier-B/C items."""

DEFAULT_RAG_SLOT_CAP_TOKENS: int = 600
"""Ceiling on what the `rag:` slot may spend, applied even at the unconstrained window.

A RAG payload is a whole node property dict. `embedding` is stripped at serialization by
NON_PROMPT_NODE_FIELDS; `biography` is not, and one retrieved Character can carry a
biography larger than every other tier-B item combined. "Measure the ceiling" must not
mean "let one slot define it" — the point of the P5 window is to observe what the
context system WANTS, and a single unbounded slot answers a different question.

Not a tuning value derived from measurement: it is a guard, set at roughly the tier's
share of the pre-P5 budget, and P10 re-decides it against the measured ceiling.
"""


class RetrievalProfile(BaseModel):
    """One named retrieval configuration.

    Attributes:
        weight_profile: Name of the relevance-weight set to apply, resolved by
            LLMConfig.resolve_weights(). None means "let the engine decide", which today
            is topic_classifier.detect_dialogue_profile() on the player message.
        rag_top_k: Top-k for the vector-store search (embedding_index.search).
        graph_rag_top_k: Top-k for graph-augmented retrieval (graph_rag_retrieve).
        events_limit: Row limit for NPC event fetching (get_events_for_npc). NOT a RAG
            top-k despite historically sharing Settings.RAG_TOP_K with the two above —
            keeping it separate is what lets a top-k experiment leave event fetching alone.
        cross_encoder_enabled: Whether to cross-encoder rerank tier-B results.
        skip_rag: Skip tier-B retrieval entirely.
        enabled_tiers: Tiers this arm assembles at all. A disabled tier is not fetched,
            not ranked and not charged — but the serializer STILL EMITS every declared
            slot with its empty default, so the JSON schema the model sees is identical
            across arms. Two arms that differ in schema are measuring schema drift.
            Note `top_need` is a tierB slot, so a tier-A-only arm drops it as well as RAG.
        disabled_slots: Slot keys this arm withholds, by the key the declaration table
            uses (``rag:``, ``beliefs``, ...). Same schema rule: the key is emitted empty.
        slot_cap_overrides: Per-slot token ceilings, applied BEFORE ranking. Exists
            because a RAG payload is a whole node property dict — `embedding` is stripped
            at serialization by NON_PROMPT_NODE_FIELDS, `biography` is not — and
            "measure the ceiling" must not mean "let one slot define it".
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    weight_profile: str | None = None
    rag_top_k: int = Field(gt=0, le=MAX_TOP_K)
    graph_rag_top_k: int = Field(gt=0, le=MAX_TOP_K)
    events_limit: int = Field(gt=0, le=MAX_TOP_K)
    cross_encoder_enabled: bool
    skip_rag: bool = False
    enabled_tiers: frozenset[str] = ALL_CONTEXT_TIERS
    disabled_slots: frozenset[str] = frozenset()
    slot_cap_overrides: dict[str, int] = Field(default_factory=dict)

    @field_validator("enabled_tiers", "disabled_slots", mode="before")
    @classmethod
    def _coerce_to_frozenset(cls, value: Any) -> Any:
        """Accept the YAML shape (a list) as well as a set, under strict mode.

        A declared arm arrives from llm_config.retrieval_profiles as a list; strict mode
        would otherwise reject it, and an arm that cannot be declared in YAML is not an
        A/B knob.
        """
        if isinstance(value, (list, set, tuple)):
            return frozenset(value)
        return value

    @field_validator("enabled_tiers")
    @classmethod
    def _reject_unknown_tiers(cls, value: frozenset[str]) -> frozenset[str]:
        """Fail fast on a mistyped tier name rather than silently disabling a real tier."""
        unknown = value - ALL_CONTEXT_TIERS
        if unknown:
            raise ValueError(f"unknown tier(s): {sorted(unknown)}; expected {sorted(ALL_CONTEXT_TIERS)}")
        return value


def build_default_profile(*, rag_top_k: int, cross_encoder_enabled: bool) -> RetrievalProfile:
    """Build the profile that reproduces current behaviour exactly.

    One Settings.RAG_TOP_K is mapped onto all three call sites, which is what the engine
    does today. Any divergence here would make merely INTRODUCING profiles an engine
    change, and the whole point is that the default path stays byte-identical.

    The one deliberate exception is the `rag:` cap (P8 §8.5): tier B has carried zero
    items on every run ever recorded, so there is no byte-identical behaviour to
    preserve there, and an uncapped slot would define the ceiling P5 exists to measure.

    Args:
        rag_top_k: Settings.RAG_TOP_K.
        cross_encoder_enabled: Settings.CROSS_ENCODER_ENABLED.
    Returns:
        A RetrievalProfile equivalent to running with no profile at all.
    """
    return RetrievalProfile(
        weight_profile=None,
        rag_top_k=rag_top_k,
        graph_rag_top_k=rag_top_k,
        events_limit=rag_top_k,
        cross_encoder_enabled=cross_encoder_enabled,
        skip_rag=False,
        slot_cap_overrides={RAG_SLOT_KEY: DEFAULT_RAG_SLOT_CAP_TOKENS},
    )


def resolve_retrieval_profile(
    name: str | None,
    *,
    profiles: dict[str, RetrievalProfile],
    fallback: RetrievalProfile,
) -> RetrievalProfile:
    """Resolve a profile name STRICTLY: an unknown name raises, it never falls back.

    This is deliberately unlike LLMConfig.resolve_weights(), which returns defaults for an
    unrecognised profile. That leniency is correct for weights and wrong here: a run would
    record `retrieval_profile="aggressive"` while having actually used the default, so the
    arm would claim a variant it never ran. Silent divergence between what a measurement
    says it measured and what it measured is the defect class this programme exists to catch.

    Args:
        name: Requested profile name. None or the default name yield the fallback.
        profiles: Registry of declared profiles, by name.
        fallback: The profile to use for the default path.
    Returns:
        The resolved RetrievalProfile.
    Raises:
        RetrievalProfileNotFoundError: When name is neither the default nor declared.
    """
    if name is None or name == DEFAULT_RETRIEVAL_PROFILE_NAME:
        return fallback
    if name in profiles:
        return profiles[name]
    raise RetrievalProfileNotFoundError(
        requested=name,
        available=", ".join(sorted([DEFAULT_RETRIEVAL_PROFILE_NAME, *profiles])),
    )
