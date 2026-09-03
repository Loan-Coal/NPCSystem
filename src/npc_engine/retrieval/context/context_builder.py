"""
Module: context_builder
Layer: retrieval
Purpose: Orchestrates context merge, relevance scoring, budget enforcement, and serialization.
Does NOT: call LLM adapters.
Dependencies injected: EmbeddingIndex.
Used by: engines.dialogue.dialogue_handler

This module is now ORCHESTRATOR ONLY (CLAUDE.md SRP: one module, one category).
The reader, builder, model, protocol and cache-state categories it used to hold live in
context_graph_readers, context_tier_builders, context_need_models, context_protocols and
context_cache_state respectively. build_serialized_context is one cohesive async pipeline
whose stages are those modules; keep new stages there, not here. No length is quoted on
purpose - a number in prose rots, and `make check-rules` owns the limits (DEC-226, DEC-249).
"""

from __future__ import annotations

import asyncio
from typing import Any

from neo4j import AsyncSession

from npc_engine.config import Settings
from npc_engine.graph.graph_reader import (
    get_npc_location_id,
)
from npc_engine.schema.npc_profile_data_models import NpcProfileData
from npc_engine.schema.retrieval_profile_models import RetrievalProfile

from .context_budget_enforcer import ContextCompressionCache, fill_to_budget_with_report
from .context_profile_resolver import resolve_profile_for_turn, resolved_profile_name
from .context_receipt import ContextReceipt, build_context_receipt
from .context_profile_policy import apply_slot_policy, tier_enabled
from .context_cache_state import (
    _check_legacy_cache,
    _get_partial_cache_state,
    _resolve_npc_context_with_cache,
)
from .context_tier_builders import (
    _build_event_trust_map,
    _build_tier0_items,
    _build_tier_a_base,
    _build_tier_a_extended,
    _build_tier_b_c_items,
    _drop_withheld_items,
)
from .context_graph_readers import (
    _TOP_NEED_TIER_B_PRIORITY,
    _fetch_base_graph_data,
    _fetch_player_data,
    _fetch_player_memory_item,
    _fetch_rag_results,
    _fetch_top_unmet_need,
)
from .context_protocols import EmbeddingIndexProtocol
from .context_builder_helpers import (
    to_json_safe,
)
from .context_merger import ContextItem, MergedContext, merge_context
from .context_metrics import (
    record_compression_metrics,
    record_context_metrics,
    record_attributed_drop_metrics,
)
from .context_scoring import rank_tier_items
from npc_engine.retrieval.embedding.topic_classifier import detect_dialogue_profile
from npc_engine.world.time_utils import TimePoint
from npc_engine.retrieval.dialogue_context.dialogue_context_cache import DialogueContextCache, PartialDialogueContextCache
from npc_engine.schema.context_config_models import LLMConfig


# ---------------------------------------------------------------------------
# Need helpers
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Private pipeline-stage helpers
# ---------------------------------------------------------------------------



def _resolve_initial_state(character_bundle: dict[str, Any], emotion_state: dict[str, Any] | None, world_state: Any) -> tuple[dict[str, Any], TimePoint, str, str]:
    """Derive emotion snapshot, game time, and cache-key timestamps from fetched data."""
    character_payload = character_bundle.get("character")
    emotion_snapshot = emotion_state or {"current_mood": "neutral"}
    if emotion_state is None and isinstance(character_payload, dict):
        emotion_snapshot = {"current_mood": str(character_payload.get("current_mood", "neutral"))}
    current_game_time = TimePoint(
        year=world_state.year, season=world_state.season,
        day=world_state.day, time_of_day=world_state.time_of_day,
    )
    npc_ts = str(character_payload.get("last_graph_updated_at", "")) if isinstance(character_payload, dict) else ""
    world_ts = world_state.last_updated_at.isoformat() if world_state.last_updated_at else ""
    return emotion_snapshot, current_game_time, npc_ts, world_ts
















async def _maybe_cross_encode(
    settings: Settings, player_message: str, tier_b_results: list[Any], profile: RetrievalProfile,
) -> list[Any]:
    """Apply cross-encoder reranking if the profile enables it and results are non-empty.

    The rerank does synchronous sentence-transformers inference, so it is offloaded
    to a worker thread (asyncio.to_thread) to keep the event loop unblocked (ISSUE-064,
    mirroring the ISSUE-063 embedding-index fix).
    """
    if not (profile.cross_encoder_enabled and tier_b_results):
        return tier_b_results
    from npc_engine.retrieval.embedding import cross_encoder_reranker
    reranked = await asyncio.to_thread(cross_encoder_reranker.rerank, player_message, tier_b_results)
    return list(reranked)
















def _rank_and_serialize_tiers(
    tier0: list[ContextItem], tier_a_raw: list[ContextItem], tier_b_raw: list[ContextItem],
    tier_c_raw: list[ContextItem],
    vector_scores: dict[str, float], event_key_trust: dict[str, float], llm_config: LLMConfig,
    settings: Settings, compression_cache: Any, weight_profile: str, active_quest: Any,
    game_time: TimePoint | None, explicit_node_ids: frozenset[str], profile_name: str,
) -> tuple[str, ContextReceipt]:
    """Rank, merge, enforce budget, record metrics, and serialize — with the assembly receipt.

    `merged` and `final_context` are the pre- and post-budget contexts the drop and
    compression metrics already consume; the receipt is the same pair reported as data
    rather than as counters.
    """
    tier_a = rank_tier_items(items=_drop_withheld_items(tier_a_raw), llm_config=llm_config, vector_scores=vector_scores,
                             trust_scores=event_key_trust, active_quest=active_quest, game_time=game_time,
                             weight_profile=weight_profile, explicit_node_ids=explicit_node_ids)
    tier_b = rank_tier_items(items=_drop_withheld_items(tier_b_raw), llm_config=llm_config, vector_scores=vector_scores,
                             game_time=game_time, weight_profile=weight_profile, explicit_node_ids=explicit_node_ids)
    tier_c = rank_tier_items(items=_drop_withheld_items(tier_c_raw), llm_config=llm_config, vector_scores=vector_scores,
                             game_time=game_time, weight_profile=weight_profile, explicit_node_ids=explicit_node_ids)
    merged = merge_context(tier0=tier0, tier_a=tier_a, tier_b=tier_b, tier_c=tier_c)
    report = fill_to_budget_with_report(
        context=merged, llm_config=llm_config,
        prompt_token_budget=settings.PROMPT_TOKEN_BUDGET, compression_cache=compression_cache,
    )
    record_context_metrics(context=report.context)
    record_compression_metrics(pre_budget_context=merged, post_budget_context=report.context)
    record_attributed_drop_metrics(report.dropped)
    receipt = build_context_receipt(
        profile_name=profile_name, post_budget=report.context, dropped=report.dropped,
        prompt_token_budget=settings.PROMPT_TOKEN_BUDGET,
    )
    return str(report.serialized), receipt


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------





async def _maybe_append_top_need(session: AsyncSession, npc_id: str, tier_b_raw: list[Any]) -> list[Any]:
    """Return tier_b_raw with the NPC's top unmet need appended as an optional Tier-B item, if any."""
    top_need = await _fetch_top_unmet_need(session=session, npc_id=npc_id)
    if top_need is None:
        return tier_b_raw
    need_item = ContextItem(
        key="top_need", text=top_need.model_dump_json(), tier="tierB", priority=_TOP_NEED_TIER_B_PRIORITY,
    )
    return [*tier_b_raw, need_item]


async def _maybe_append_player_memory(session: AsyncSession, npc_id: str, player_id: str | None, game_time: TimePoint | None, tier_a_raw: list[ContextItem]) -> None:
    """Append the player-scoped memory item to tier_a_raw when the NPC holds such memories."""
    item = await _fetch_player_memory_item(session, npc_id, player_id, game_time)
    if item is not None:
        tier_a_raw.append(item)


def _validated_profile_for_turn(
    settings: Settings, llm_config: LLMConfig, requested: str | None
) -> RetrievalProfile:
    """Validate retrieval settings and resolve the profile for this turn.

    Extracted from build_serialized_context purely to keep that function inside the
    40-line limit; it carries no logic of its own beyond the RAG_TOP_K guard that has
    always run first.

    Raises:
        ValueError: If RAG_TOP_K <= 0.
        RetrievalProfileNotFoundError: If the resolved profile name is not declared.
    """
    if settings.RAG_TOP_K <= 0:
        raise ValueError("RAG_TOP_K must be greater than 0")
    return resolve_profile_for_turn(settings=settings, llm_config=llm_config, requested=requested)




async def _build_all_tier_a_items(
    session: AsyncSession, npc_id: str, player_id: str | None, settings: Settings,
    character_bundle: Any, profile_data: NpcProfileData, session_turns: list[str],
    location_id: str | None, beliefs: Any, goals: Any, secrets: Any, obligations: Any,
    second_hop_events: Any, active_quest: Any, player_relation_edge: Any,
    propagated_reputation: Any, game_time: TimePoint | None,
) -> list[ContextItem]:
    """Assemble every tier-A item: the base set, the extended set, and player memories."""
    items = _build_tier_a_base(
        npc_id, character_bundle, profile_data.events, location_id,
        profile_data.location_context, profile_data.group_memberships,
        profile_data.believed_rumors, profile_data.traits, profile_data.active_pledges,
        session_turns,
    )
    items.extend(_build_tier_a_extended(
        player_id, profile_data.reputation_items, active_quest, player_relation_edge,
        profile_data.memories, beliefs, goals, profile_data.owned_items, secrets,
        obligations, second_hop_events, settings, npc_id, game_time, propagated_reputation,
    ))
    await _maybe_append_player_memory(session, npc_id, player_id, game_time, items)
    return items


async def _apply_profile_policy(
    session: AsyncSession, npc_id: str,
    profile: RetrievalProfile, llm_config: LLMConfig, compression_cache: Any,
    tier0: list[ContextItem], tier_a: list[ContextItem],
    tier_b: list[ContextItem], tier_c: list[ContextItem],
) -> tuple[list[ContextItem], list[ContextItem], list[ContextItem], list[ContextItem]]:
    """Gate each tier on the arm and apply its slot policy; return the four lists.

    A disabled tier is emptied HERE rather than at its producer so that exactly one
    place decides it, and so that the serializer — which is unaware of profiles — goes
    on emitting every declared slot's empty default. Schema stable, content varying.

    `top_need` is fetched inside this gate because it is a tierB slot: a tier-A-only arm
    must not pay for a graph read whose result it then discards.
    """
    if tier_enabled(profile, "tierB"):
        tier_b = await _maybe_append_top_need(session, npc_id, tier_b)
    cache = compression_cache if compression_cache is not None else ContextCompressionCache()
    gated = [
        items if tier_enabled(profile, tier) else []
        for tier, items in (
            ("tier0", tier0), ("tierA", tier_a), ("tierB", tier_b), ("tierC", tier_c)
        )
    ]
    filtered = [
        apply_slot_policy(items, profile=profile, llm_config=llm_config, compression_cache=cache)
        for items in gated
    ]
    return filtered[0], filtered[1], filtered[2], filtered[3]


async def build_serialized_context_with_receipt(
    session: AsyncSession, settings: Settings, llm_config: LLMConfig, embedding_index: EmbeddingIndexProtocol,
    npc_id: str, player_message: str, session_turns: list[str], emotion_state: dict[str, Any] | None = None,
    compression_cache: ContextCompressionCache | None = None,
    context_cache: PartialDialogueContextCache | DialogueContextCache | None = None,
    session_id: str | None = None, skip_rag: bool = False, player_id: str | None = None,
    weight_profile: str | None = None, explicit_node_ids: frozenset[str] = frozenset(),
    system_state_context: Any | None = None, retrieval_profile: str | None = None,
) -> tuple[str, ContextReceipt | None]:
    """Build one turn's serialized context plus its receipt (None only on a legacy cache hit)."""
    active_profile = _validated_profile_for_turn(settings, llm_config, retrieval_profile)
    character_bundle, world_state, known_event_ids = await _fetch_base_graph_data(session, npc_id)
    emotion_snapshot, current_game_time, npc_ts, world_ts = _resolve_initial_state(character_bundle, emotion_state, world_state)
    cache_hit, legacy_cache, legacy_key = _check_legacy_cache(context_cache, session_id, npc_id, player_id, emotion_snapshot, npc_ts, world_ts)
    if cache_hit is not None:
        return str(cache_hit), None
    active_profile_name = resolved_profile_name(settings=settings, requested=retrieval_profile)
    partial_cache, profile_key, bg_key, cached_profile, cached_bg = _get_partial_cache_state(context_cache, npc_id, npc_ts, active_profile_name)
    location_id = await get_npc_location_id(session=session, npc_id=npc_id)
    tier_b_results = await _fetch_rag_results(session, embedding_index, settings, player_message, session_turns, known_event_ids, npc_id, current_game_time, skip_rag, active_profile)
    profile_data, beliefs, goals, secrets, obligations = await _resolve_npc_context_with_cache(session, npc_id, settings, player_id, location_id, partial_cache, profile_key, bg_key, cached_profile, cached_bg, player_message, active_profile)
    trust_scores, second_hop_events, active_quest, player_relation_edge, propagated_reputation = await _fetch_player_data(session, npc_id, player_id, profile_data.events)
    tier_b_results = await _maybe_cross_encode(settings, player_message, tier_b_results, active_profile)
    tier0 = _build_tier0_items(world_state, emotion_snapshot, system_state_context)
    tier_a_raw = await _build_all_tier_a_items(session, npc_id, player_id, settings, character_bundle, profile_data, session_turns, location_id, beliefs, goals, secrets, obligations, second_hop_events, active_quest, player_relation_edge, propagated_reputation, current_game_time)
    tier_b_raw, tier_c_raw, vector_scores = _build_tier_b_c_items(tier_b_results)
    tier0, tier_a_raw, tier_b_raw, tier_c_raw = await _apply_profile_policy(session, npc_id, active_profile, llm_config, compression_cache, tier0, tier_a_raw, tier_b_raw, tier_c_raw)
    event_key_trust = _build_event_trust_map(profile_data.events, trust_scores, npc_id)
    serialized, receipt = _rank_and_serialize_tiers(
        tier0=tier0, tier_a_raw=tier_a_raw, tier_b_raw=tier_b_raw, tier_c_raw=tier_c_raw,
        vector_scores=vector_scores, event_key_trust=event_key_trust, llm_config=llm_config,
        settings=settings, compression_cache=compression_cache, weight_profile=weight_profile or active_profile.weight_profile or detect_dialogue_profile(player_message),
        active_quest=active_quest, game_time=current_game_time, explicit_node_ids=explicit_node_ids,
        profile_name=active_profile_name,
    )
    if legacy_cache is not None and legacy_key is not None:
        legacy_cache.set(legacy_key, serialized)
    return serialized, receipt


async def build_serialized_context(
    session: AsyncSession, settings: Settings, llm_config: LLMConfig, embedding_index: EmbeddingIndexProtocol,
    npc_id: str, player_message: str, session_turns: list[str], emotion_state: dict[str, Any] | None = None,
    compression_cache: ContextCompressionCache | None = None,
    context_cache: PartialDialogueContextCache | DialogueContextCache | None = None,
    session_id: str | None = None, skip_rag: bool = False, player_id: str | None = None,
    weight_profile: str | None = None, explicit_node_ids: frozenset[str] = frozenset(),
    system_state_context: Any | None = None, retrieval_profile: str | None = None,
) -> str:
    """Build the serialized prompt context for one dialogue turn, discarding the receipt.

    The receipt-free entry point every caller that only needs prompt text keeps using;
    `retrieval_profile` selects the A/B arm (see _validated_profile_for_turn). Every
    argument is forwarded by keyword, so mypy fails the build if the two signatures drift.
    """
    serialized, _receipt = await build_serialized_context_with_receipt(
        session=session, settings=settings, llm_config=llm_config, embedding_index=embedding_index,
        npc_id=npc_id, player_message=player_message, session_turns=session_turns,
        emotion_state=emotion_state, compression_cache=compression_cache, context_cache=context_cache,
        session_id=session_id, skip_rag=skip_rag, player_id=player_id, weight_profile=weight_profile,
        explicit_node_ids=explicit_node_ids, system_state_context=system_state_context,
        retrieval_profile=retrieval_profile,
    )
    return serialized


def _to_json_safe(value: Any) -> Any:
    """Delegate to the helpers module for backward compatibility."""
    return to_json_safe(value)


# Backward-compatibility shims for tests that import these names directly.
def _enforce_final_serialized_budget(context: MergedContext, budget: int) -> str:
    from .context_builder_helpers import enforce_final_serialized_budget_with_context
    _, serialized = enforce_final_serialized_budget_with_context(context=context, budget=budget)
    return serialized


def _estimate_tokens(text: str) -> int:
    from .context_utils import estimate_tokens
    return estimate_tokens(text)
