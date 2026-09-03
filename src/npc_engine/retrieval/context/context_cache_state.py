"""
Module: context_cache_state
Layer: retrieval
Purpose: Resolve a dialogue turn's NPC context against the legacy and partial context caches.
Does NOT: read the graph, build items, rank, budget or serialize - cache lookup and bookkeeping only.
Dependencies: retrieval.dialogue_context caches, context_metrics, context_profile_resolver.
Dependencies injected: DialogueContextCache and PartialDialogueContextCache are passed per call.
Used by: retrieval.context.context_builder
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.config import Settings
from npc_engine.retrieval.dialogue_context.dialogue_context_cache import (
    DialogueContextCache,
    PartialDialogueContextCache,
)
from npc_engine.schema.npc_profile_data_models import NpcProfileData
from npc_engine.schema.retrieval_profile_models import RetrievalProfile
from npc_engine.utils.metrics import increment_metric

from .context_builder_helpers import rerank_by_keyword
from .context_graph_readers import _fetch_beliefs_goals_data, _fetch_npc_profile_data
from .context_metrics import CONTEXT_CACHE_HITS_METRIC, CONTEXT_CACHE_MISSES_METRIC


def _check_legacy_cache(
    context_cache: Any, session_id: str | None, npc_id: str, player_id: str | None,
    emotion_snapshot: dict[str, Any], npc_ts: str, world_ts: str,
) -> tuple[str | None, Any, Any]:
    """Check the legacy monolithic cache; return (hit_string | None, legacy_cache, legacy_key)."""
    legacy_cache: DialogueContextCache | None = (
        context_cache if isinstance(context_cache, DialogueContextCache) else None
    )
    if legacy_cache is None or session_id is None:
        return None, legacy_cache, None
    legacy_key = legacy_cache.build_key(
        npc_id=npc_id, session_id=session_id, player_id=player_id or "",
        npc_last_graph_updated_at=npc_ts, world_last_updated_at=world_ts,
        current_mood=str(emotion_snapshot.get("current_mood", "neutral")),
    )
    cached = legacy_cache.get(legacy_key)
    if cached is not None:
        increment_metric(metric=CONTEXT_CACHE_HITS_METRIC, labels={"npc_id": npc_id})
        return cached, legacy_cache, legacy_key
    increment_metric(metric=CONTEXT_CACHE_MISSES_METRIC, labels={"npc_id": npc_id})
    return None, legacy_cache, legacy_key
def _get_partial_cache_state(
    context_cache: Any, npc_id: str, npc_ts: str, profile_name: str
) -> tuple[Any, Any, Any, Any, Any]:
    """Extract partial cache and its keys; record hit/miss metrics when both slots are warm.

    `profile_name` reaches the PROFILE key only. The value cached there is read with the
    profile's own `events_limit`, so two A/B arms sharing an entry means the second arm is
    served the first arm's event list -- and with the arms interleaved inside one run, that
    reads as a treatment effect. The beliefs/goals key deliberately omits it; see
    `build_beliefs_goals_key`.
    """
    partial_cache: PartialDialogueContextCache | None = (
        context_cache if isinstance(context_cache, PartialDialogueContextCache) else None
    )
    if partial_cache is None:
        return None, None, None, None, None
    profile_key = partial_cache.build_profile_key(
        npc_id=npc_id, npc_last_graph_updated_at=npc_ts, profile_name=profile_name
    )
    bg_key = partial_cache.build_beliefs_goals_key(npc_id=npc_id, npc_last_graph_updated_at=npc_ts)
    cached_profile = partial_cache.get_profile(profile_key)
    cached_bg = partial_cache.get_beliefs_goals(bg_key)
    if cached_profile is not None and cached_bg is not None:
        increment_metric(metric=CONTEXT_CACHE_HITS_METRIC, labels={"npc_id": npc_id})
    else:
        increment_metric(metric=CONTEXT_CACHE_MISSES_METRIC, labels={"npc_id": npc_id})
    return partial_cache, profile_key, bg_key, cached_profile, cached_bg
async def _resolve_npc_context_with_cache(
    session: AsyncSession, npc_id: str, settings: Settings, player_id: str | None,
    location_id: str | None, partial_cache: Any, profile_key: Any, bg_key: Any,
    cached_profile: Any, cached_bg: Any,
    player_message: str, retrieval_profile: RetrievalProfile,
) -> tuple[NpcProfileData, Any, Any, Any, Any]:
    """Fetch or restore profile+beliefs/goals with partial cache; return (profile_data, beliefs, goals, secrets, obligations)."""
    profile_miss = cached_profile is None
    bg_miss = cached_bg is None
    if profile_miss and bg_miss:
        new_profile = await _fetch_npc_profile_data(session, npc_id, settings, player_id, location_id, retrieval_profile)
        new_bg = await _fetch_beliefs_goals_data(session, npc_id)
    elif profile_miss:
        new_profile = await _fetch_npc_profile_data(session, npc_id, settings, player_id, location_id, retrieval_profile)
        new_bg = None
    elif bg_miss:
        new_profile = None
        new_bg = await _fetch_beliefs_goals_data(session, npc_id)
    else:
        new_profile = new_bg = None
    if new_profile is not None and partial_cache is not None and profile_key is not None:
        partial_cache.set_profile(profile_key, new_profile)
    profile_data = new_profile if new_profile is not None else cached_profile
    if new_bg is not None and partial_cache is not None and bg_key is not None:
        partial_cache.set_beliefs_goals(bg_key, new_bg)
    bg_data = new_bg if new_bg is not None else cached_bg
    beliefs, goals, secrets, obligations = bg_data
    return (profile_data,
            rerank_by_keyword(beliefs, "content", player_message, top_k=3),
            rerank_by_keyword(goals, "objective", player_message, top_k=3),
            rerank_by_keyword(secrets, "content", player_message, top_k=3),
            obligations)
