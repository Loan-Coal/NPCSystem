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

from pydantic import BaseModel, ConfigDict, Field

from npc_engine.utils.errors import RetrievalProfileNotFoundError

__all__ = [
    "DEFAULT_RETRIEVAL_PROFILE_NAME",
    "MAX_TOP_K",
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
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    weight_profile: str | None = None
    rag_top_k: int = Field(gt=0, le=MAX_TOP_K)
    graph_rag_top_k: int = Field(gt=0, le=MAX_TOP_K)
    events_limit: int = Field(gt=0, le=MAX_TOP_K)
    cross_encoder_enabled: bool
    skip_rag: bool = False


def build_default_profile(*, rag_top_k: int, cross_encoder_enabled: bool) -> RetrievalProfile:
    """Build the profile that reproduces current behaviour exactly.

    One Settings.RAG_TOP_K is mapped onto all three call sites, which is what the engine
    does today. Any divergence here would make merely INTRODUCING profiles an engine
    change, and the whole point is that the default path stays byte-identical.

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
