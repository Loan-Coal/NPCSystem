"""
Module: context_profile_resolver
Layer: retrieval
Purpose: Resolve the RetrievalProfile a dialogue turn runs under, from the per-request
         override, the deployment default, and the engine's declared registry.
Dependencies: npc_engine.config (Settings), npc_engine.schema.context_config_models
              (LLMConfig), npc_engine.schema.retrieval_profile_models
Used by: context_builder (profile resolution and the receipt's profile name)

Does NOT: perform retrieval or touch the graph. Lives in its own module because
context_builder.py is already past the 300-line cap and must not grow.

Dependencies injected: Settings and LLMConfig are passed in per call; nothing is read
from module-level state.

Precedence is request > deployment default > built-from-Settings fallback. The fallback
reproduces today's behaviour exactly (one RAG_TOP_K mapped onto all three call sites), so
a turn with no profile is byte-identical to a turn from before profiles existed.
"""

from __future__ import annotations

from npc_engine.config import Settings
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.schema.retrieval_profile_models import RetrievalProfile, build_default_profile


def resolve_profile_for_turn(
    *,
    settings: Settings,
    llm_config: LLMConfig,
    requested: str | None,
) -> RetrievalProfile:
    """Resolve the profile for one dialogue turn.

    Args:
        settings: Engine settings, supplying the deployment default and the values the
            fallback profile is built from.
        llm_config: Engine LLM config carrying the declared profile registry.
        requested: Per-request override; None falls back to settings.RETRIEVAL_PROFILE.
    Returns:
        The resolved RetrievalProfile.
    Raises:
        RetrievalProfileNotFoundError: When the resolved name is neither the default nor
            declared in llm_config.retrieval_profiles. Deliberately not a fallback — see
            retrieval_profile_models.resolve_retrieval_profile.
    """
    fallback = build_default_profile(
        rag_top_k=settings.RAG_TOP_K,
        cross_encoder_enabled=settings.CROSS_ENCODER_ENABLED,
    )
    name = resolved_profile_name(settings=settings, requested=requested)
    return llm_config.resolve_retrieval_profile(name, fallback=fallback)


def resolved_profile_name(*, settings: Settings, requested: str | None) -> str:
    """Return the profile NAME this turn resolves to, without resolving the profile itself.

    Kept beside resolve_profile_for_turn and derived from the same precedence rule so the
    two cannot disagree: a receipt naming one arm while the assembly used another would be
    worse than no receipt at all.

    Args:
        settings: Engine settings, supplying the deployment default.
        requested: Per-request override; None falls back to settings.RETRIEVAL_PROFILE.
    Returns:
        The resolved profile name. No validation — resolve_profile_for_turn owns the
        strict check and raises for both callers.
    """
    return requested if requested is not None else settings.RETRIEVAL_PROFILE
