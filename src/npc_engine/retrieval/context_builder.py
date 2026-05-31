"""
Module: context_builder
Layer: retrieval
Purpose: Orchestrates context merge, relevance scoring, budget enforcement, and serialization.
Does NOT: call LLM adapters.
Dependencies injected: EmbeddingIndex.
Used by: engines.dialogue.dialogue_handler

NOTE: This file exceeds the 300-line limit (currently ~367 lines). The single public function
build_serialized_context is an async pipeline — every line is part of one cohesive orchestration
flow. Splitting it would create helpers with no encapsulation value. See DECISIONS.md entry
"context_builder.py exceeds 300-line limit (Phase 6)" for the full analysis.
"""

from __future__ import annotations

import logging
import time
from typing import Protocol

logger = logging.getLogger(__name__)

from neo4j import AsyncSession

from npc_engine.config import Settings
from npc_engine.graph.graph_reader import (
    get_character_with_relations,
    get_events_for_npc,
    get_known_event_ids_for_npc,
    get_location_context,
    get_npc_location_id,
)
from npc_engine.graph.belief_queries import get_beliefs_for_character
from npc_engine.graph.goal_queries import get_goals_for_character
from npc_engine.graph.item_queries import get_items_for_character
from npc_engine.graph.secret_queries import get_secrets_for_character
from npc_engine.graph.owes_queries import get_debts_for_character
from npc_engine.graph.group_service import get_groups_for_character_svc
from npc_engine.graph.rumor_service import get_rumors_for_character_svc
from npc_engine.graph.trait_service import get_traits_svc
from npc_engine.graph.pledge_service import get_pledges_for_character_svc
from npc_engine.graph.memory_queries import get_memories_for_character
from npc_engine.graph.reputation_queries import get_reputation_context_for_npc
from npc_engine.graph.trust_queries import get_second_hop_events, get_trust_scores_for_events
from npc_engine.graph.quest_queries import get_active_quest_for_player, get_offered_quests_for_npc
from npc_engine.graph.interaction_queries import get_sellable_items_for_npc
from npc_engine.retrieval.context_budget_enforcer import ContextCompressionCache, fill_to_budget
from npc_engine.retrieval.context_builder_helpers import (
    expand_query,
    normalize_ratio,
    rerank_by_keyword,
    to_json_safe,
)
from npc_engine.retrieval.context_merger import ContextItem, MergedContext, merge_context
from npc_engine.retrieval.context_metrics import (
    CONTEXT_CACHE_HITS_METRIC,
    CONTEXT_CACHE_MISSES_METRIC,
    record_compression_metrics,
    record_context_metrics,
)
from npc_engine.retrieval.context_scoring import rank_tier_items
from npc_engine.retrieval.graph_rag import graph_rag_retrieve
from npc_engine.retrieval.topic_classifier import detect_dialogue_profile
from npc_engine.world.time_utils import TimePoint
from npc_engine.retrieval.context_utils import serialize_json
from npc_engine.retrieval.dialogue_context_cache import DialogueContextCache, PartialDialogueContextCache
from npc_engine.retrieval.subgraph_retriever import assemble_tier_a_context
from npc_engine.retrieval.vector_store_protocol import VectorSearchResult
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.utils.metrics import increment_metric
from npc_engine.world.world_reader import get_world_state


class EmbeddingIndexProtocol(Protocol):
    """Minimal protocol required by context builder."""

    async def search(
        self,
        query: str,
        top_k: int,
        filter_ids: set[str] | None = None,
    ) -> list[VectorSearchResult]:
        """Return top-k semantic retrieval rows.

        Args:
            query: Text query to embed and search.
            top_k: Maximum number of results to return.
            filter_ids: When provided, restrict results to items with these IDs.

        Returns:
            List of VectorSearchResult dicts sorted by descending score.
        """


async def build_serialized_context(
    session: AsyncSession,
    settings: Settings,
    llm_config: LLMConfig,
    embedding_index: EmbeddingIndexProtocol,
    npc_id: str,
    player_message: str,
    session_turns: list[str],
    emotion_state: dict | None = None,
    compression_cache: ContextCompressionCache | None = None,
    context_cache: PartialDialogueContextCache | DialogueContextCache | None = None,
    session_id: str | None = None,
    skip_rag: bool = False,
    player_id: str | None = None,
    weight_profile: str | None = None,
    explicit_node_ids: frozenset[str] = frozenset(),
) -> str:
    """Build the final serialized prompt context string for one dialogue turn.

    Issues graph queries sequentially (single session), applies relevance
    scoring, budget enforcement, and serializes to compact JSON.

    Raises:
        ValueError: If RAG_TOP_K is not greater than 0.
        ContextBudgetError: If tier A or total prompt budget cannot be satisfied.
    """

    _t0 = time.perf_counter()

    if settings.RAG_TOP_K <= 0:
        raise ValueError("RAG_TOP_K must be greater than 0")

    # Stage 1: sequential queries — Neo4j AsyncSession is not safe for concurrent use.
    # TODO (Phase 5 B1): To run Stage 1-4 batches concurrently, accept an AsyncDriver
    # parameter and open one session per batch. asyncio.gather on a single session
    # causes BufferError in the neo4j async driver.
    character_bundle = await get_character_with_relations(session=session, npc_id=npc_id)
    world_state = await get_world_state(session=session)
    known_event_ids = await get_known_event_ids_for_npc(session=session, npc_id=npc_id)

    character_payload = character_bundle.get("character")
    emotion_snapshot = emotion_state or {"current_mood": "neutral"}
    if emotion_state is None and isinstance(character_payload, dict):
        emotion_snapshot = {
            "current_mood": str(character_payload.get("current_mood", "neutral")),
        }

    current_game_time = TimePoint(
        year=world_state.year,
        season=world_state.season,
        day=world_state.day,
        time_of_day=world_state.time_of_day,
    )

    # Derive cache keys (used by both legacy and partial cache paths).
    npc_ts = str(character_payload.get("last_graph_updated_at", "")) if isinstance(character_payload, dict) else ""
    world_ts = world_state.last_updated_at.isoformat() if world_state.last_updated_at else ""

    # Legacy monolithic cache path — backward-compat for callers still passing DialogueContextCache.
    legacy_cache: DialogueContextCache | None = context_cache if isinstance(context_cache, DialogueContextCache) else None
    if legacy_cache is not None and session_id is not None:
        legacy_key = legacy_cache.build_key(
            npc_id=npc_id,
            session_id=session_id,
            player_id=player_id or "",
            npc_last_graph_updated_at=npc_ts,
            world_last_updated_at=world_ts,
            current_mood=str(emotion_snapshot.get("current_mood", "neutral")),
        )
        cached = legacy_cache.get(legacy_key)
        if cached is not None:
            increment_metric(metric=CONTEXT_CACHE_HITS_METRIC, labels={"npc_id": npc_id})
            return cached
        increment_metric(metric=CONTEXT_CACHE_MISSES_METRIC, labels={"npc_id": npc_id})
    else:
        legacy_key = None

    # Sub-cache path — PartialDialogueContextCache splits profile and beliefs/goals.
    partial_cache: PartialDialogueContextCache | None = (
        context_cache if isinstance(context_cache, PartialDialogueContextCache) else None
    )
    profile_key = bg_key = None
    cached_profile_data = cached_bg_data = None
    if partial_cache is not None:
        profile_key = partial_cache.build_profile_key(npc_id=npc_id, npc_last_graph_updated_at=npc_ts)
        bg_key = partial_cache.build_beliefs_goals_key(npc_id=npc_id, npc_last_graph_updated_at=npc_ts)
        cached_profile_data = partial_cache.get_profile(profile_key)
        cached_bg_data = partial_cache.get_beliefs_goals(bg_key)
        if cached_profile_data is not None and cached_bg_data is not None:
            increment_metric(metric=CONTEXT_CACHE_HITS_METRIC, labels={"npc_id": npc_id})
        else:
            increment_metric(metric=CONTEXT_CACHE_MISSES_METRIC, labels={"npc_id": npc_id})

    # Stage 2: location_id then optional vector search — session must be used sequentially.
    rag_filter = known_event_ids if known_event_ids else None
    rag_query = expand_query(player_message, session_turns)
    location_id = await get_npc_location_id(session=session, npc_id=npc_id)
    if not skip_rag:
        if settings.GRAPH_RAG_ENABLED:
            tier_b_results = await graph_rag_retrieve(
                session=session,
                embedding_index=embedding_index,
                query=rag_query,
                npc_id=npc_id,
                known_event_ids=known_event_ids or set(),
                top_k=settings.RAG_TOP_K,
                game_time=current_game_time,
            )
        else:
            tier_b_results = await embedding_index.search(
                query=rag_query, top_k=settings.RAG_TOP_K, filter_ids=rag_filter
            )
    else:
        tier_b_results = []

    # Stage 3: graph queries, skipping sub-caches that are warm.
    # All queries use the same session sequentially — concurrent use causes BufferError.
    async def _fetch_profile() -> tuple:
        location_context = await get_location_context(session=session, location_id=location_id)
        events = await get_events_for_npc(session=session, npc_id=npc_id, limit=settings.RAG_TOP_K)
        reputation_items = await get_reputation_context_for_npc(
            session,
            npc_id=npc_id,
            player_id=player_id or "",
            threshold=settings.REPUTATION_CONTEXT_THRESHOLD,
        )
        memories = await get_memories_for_character(session, character_id=npc_id, k=3)
        owned_items = await get_items_for_character(session, character_id=npc_id, k=10)
        group_memberships = await get_groups_for_character_svc(session, character_id=npc_id)
        believed_rumors = await get_rumors_for_character_svc(session, character_id=npc_id, min_confidence=30)
        traits = await get_traits_svc(session, npc_id)
        active_pledges = await get_pledges_for_character_svc(session, npc_id, active_only=True)
        return (location_context, events, reputation_items, memories,
                owned_items, group_memberships, believed_rumors, traits, active_pledges)

    async def _fetch_beliefs_goals() -> tuple:
        beliefs = await get_beliefs_for_character(session, character_id=npc_id, k=10)
        goals = await get_goals_for_character(session, character_id=npc_id, k=10, status_filter="active")
        secrets = await get_secrets_for_character(session, character_id=npc_id, k=10)
        obligations = await get_debts_for_character(session, character_id=npc_id, k=5)
        return beliefs, goals, secrets, obligations

    profile_miss = cached_profile_data is None
    bg_miss = cached_bg_data is None

    if profile_miss and bg_miss:
        new_profile = await _fetch_profile()
        new_bg = await _fetch_beliefs_goals()
    elif profile_miss:
        new_profile = await _fetch_profile()
        new_bg = None
    elif bg_miss:
        new_profile = None
        new_bg = await _fetch_beliefs_goals()
    else:
        new_profile = new_bg = None

    if new_profile is not None:
        (location_context, events, reputation_items, memories,
         owned_items, group_memberships, believed_rumors, traits, active_pledges) = new_profile
        if partial_cache is not None and profile_key is not None:
            partial_cache.set_profile(profile_key, new_profile)
    else:
        (location_context, events, reputation_items, memories,
         owned_items, group_memberships, believed_rumors, traits, active_pledges) = cached_profile_data  # type: ignore[misc]

    if new_bg is not None:
        beliefs, goals, secrets, obligations = new_bg
        if partial_cache is not None and bg_key is not None:
            partial_cache.set_beliefs_goals(bg_key, new_bg)
    else:
        beliefs, goals, secrets, obligations = cached_bg_data  # type: ignore[misc]

    # 6.1 Two-pass rerank: fetch top-10 by intrinsic score, keep top-3 by keyword overlap.
    beliefs = rerank_by_keyword(beliefs, "content", player_message, top_k=3)
    goals = rerank_by_keyword(goals, "objective", player_message, top_k=3)
    secrets = rerank_by_keyword(secrets, "content", player_message, top_k=3)

    # Stage 4: trust scores + second-hop events + player quest state (depends on Stage 3).
    event_ids = [str(e["id"]) for e in events if e.get("id")]

    trust_scores = await get_trust_scores_for_events(session, npc_id=npc_id, event_ids=event_ids)
    second_hop_events = await get_second_hop_events(session, npc_id=npc_id)
    active_quest = await get_active_quest_for_player(session, player_id=player_id) if player_id else None
    npc_offered_quests = await get_offered_quests_for_npc(session, npc_id=npc_id)
    npc_sellable_items = await get_sellable_items_for_npc(session, npc_id=npc_id)

    # 6.5: Cross-encoder rerank Tier B/C vector results before building ContextItems.
    if settings.CROSS_ENCODER_ENABLED and tier_b_results:
        from npc_engine.retrieval.cross_encoder_reranker import rerank as cross_encode_rerank
        tier_b_results = cross_encode_rerank(player_message, tier_b_results)

    # Assemble tiers from pre-fetched data
    tier0 = [
        ContextItem(key="world", text=world_state.model_dump_json(), tier="tier0", priority=100),
        ContextItem(key="emotion", text=serialize_json(emotion_snapshot), tier="tier0", priority=95),
    ]

    tier_a_raw = [
        ContextItem(key="session", text=serialize_json(session_turns), tier="tierA", priority=99),
    ]
    tier_a_raw.extend(
        assemble_tier_a_context(
            npc_id=npc_id,
            character_bundle=character_bundle,
            events=events,
            location_id=location_id,
            location_context=location_context,
            group_memberships=group_memberships or [],
            believed_rumors=believed_rumors or [],
            traits=traits or [],
            active_pledges=active_pledges or [],
        )
    )

    if player_id is not None and reputation_items:
        tier_a_raw.append(
            ContextItem(
                key="reputation",
                text=serialize_json(reputation_items),
                tier="tierA",
                priority=85,
            )
        )

    if active_quest:
        tier_a_raw.append(ContextItem(key="active_quest", text=serialize_json(active_quest), tier="tierA", priority=89))
    if npc_offered_quests:
        tier_a_raw.append(ContextItem(
            key="npc_offered_quests",
            text=serialize_json(npc_offered_quests),
            tier="tierA",
            priority=92,
        ))
    if npc_sellable_items or npc_offered_quests:
        available_interactions: list[dict] = []
        if npc_sellable_items:
            available_interactions.append({"kind": "propose_trade", "items": [i["id"] for i in npc_sellable_items]})
            tier_a_raw.append(ContextItem(
                key="npc_inventory_for_sale",
                text=serialize_json(npc_sellable_items),
                tier="tierA",
                priority=91,
            ))
        if npc_offered_quests:
            for q in npc_offered_quests:
                available_interactions.append({"kind": "propose_quest", "quest_id": q.get("id")})
        tier0.append(ContextItem(
            key="available_interactions",
            text=serialize_json(available_interactions),
            tier="tier0",
            priority=96,
        ))
    if memories:
        tier_a_raw.append(ContextItem(key="memories", text=serialize_json(memories), tier="tierA", priority=90))
    if beliefs:
        tier_a_raw.append(ContextItem(key="beliefs", text=serialize_json(beliefs), tier="tierA", priority=88))
    if goals:
        tier_a_raw.append(ContextItem(key="goals", text=serialize_json(goals), tier="tierA", priority=87))
    if owned_items:
        tier_a_raw.append(ContextItem(key="owned_items", text=serialize_json(owned_items), tier="tierA", priority=86))
    if secrets:
        tier_a_raw.append(ContextItem(key="secrets", text=serialize_json(secrets), tier="tierA", priority=84))
    if obligations:
        tier_a_raw.append(ContextItem(key="obligations", text=serialize_json(obligations), tier="tierA", priority=83))
    # 6.6: second-hop events from trusted friends at lower priority than direct events.
    for idx, evt in enumerate(second_hop_events or []):
        tier_a_raw.append(
            ContextItem(
                key=f"second_hop:{idx}:{npc_id}",
                text=serialize_json(_to_json_safe(evt), strip_nulls=True),
                tier="tierA",
                priority=74 - idx,
            )
        )

    tier_b_raw: list[ContextItem] = []
    tier_c_raw: list[ContextItem] = []
    vector_scores: dict[str, float] = {}
    if tier_b_results:
        split_index = max(1, len(tier_b_results) // 2) if len(tier_b_results) > 0 else 0
        for index, row in enumerate(tier_b_results):
            item = ContextItem(
                key=f"rag:{row['id']}",
                text=serialize_json(_to_json_safe(row["payload"])),
                tier="tierB" if index < split_index else "tierC",
                priority=max(1, 60 - index),
            )
            if item.tier == "tierB":
                tier_b_raw.append(item)
            else:
                tier_c_raw.append(item)
        vector_scores = {
            f"rag:{row['id']}": normalize_ratio(float(row.get("score", 0.0)))
            for row in tier_b_results
        }

    # Map trust_scores from event_ids back to ContextItem keys ("event:{index}:{npc_id}").
    # Trust query returns event_id → score; ContextItem keys use positional index, not id.
    # Build a mapping from event index to trust score via the events list order.
    event_key_trust: dict[str, float] = {}
    for idx, evt in enumerate(events):
        eid = str(evt.get("id", ""))
        if eid in trust_scores:
            event_key_trust[f"event:{idx}:{npc_id}"] = trust_scores[eid]

    resolved_profile = weight_profile or detect_dialogue_profile(player_message)
    tier_a = rank_tier_items(
        items=tier_a_raw,
        llm_config=llm_config,
        vector_scores=vector_scores,
        trust_scores=event_key_trust,
        active_quest=active_quest,
        game_time=current_game_time,
        weight_profile=resolved_profile,
        explicit_node_ids=explicit_node_ids,
    )
    tier_b = rank_tier_items(
        items=tier_b_raw,
        llm_config=llm_config,
        vector_scores=vector_scores,
        game_time=current_game_time,
        weight_profile=resolved_profile,
        explicit_node_ids=explicit_node_ids,
    )
    tier_c = rank_tier_items(
        items=tier_c_raw,
        llm_config=llm_config,
        vector_scores=vector_scores,
        game_time=current_game_time,
        weight_profile=resolved_profile,
        explicit_node_ids=explicit_node_ids,
    )

    merged = merge_context(tier0=tier0, tier_a=tier_a, tier_b=tier_b, tier_c=tier_c)
    final_context, serialized = fill_to_budget(
        context=merged,
        llm_config=llm_config,
        prompt_token_budget=settings.PROMPT_TOKEN_BUDGET,
        compression_cache=compression_cache,
    )
    record_context_metrics(context=final_context)
    record_compression_metrics(pre_budget_context=merged, post_budget_context=final_context)

    if legacy_cache is not None and legacy_key is not None:
        legacy_cache.set(legacy_key, serialized)

    elapsed_ms = (time.perf_counter() - _t0) * 1000
    logger.info("context_build_ms npc_id=%s elapsed_ms=%.1f", npc_id, elapsed_ms)

    return serialized


def _to_json_safe(value):
    """Delegate to the helpers module for backward compatibility."""
    return to_json_safe(value)


# Backward-compatibility shims for tests that import these names directly.
def _enforce_final_serialized_budget_with_context(context: MergedContext, budget: int) -> tuple[MergedContext, str]:
    from npc_engine.retrieval.context_builder_helpers import enforce_final_serialized_budget_with_context
    return enforce_final_serialized_budget_with_context(context=context, budget=budget)


def _enforce_final_serialized_budget(context: MergedContext, budget: int) -> str:
    from npc_engine.retrieval.context_builder_helpers import enforce_final_serialized_budget_with_context
    _, serialized = enforce_final_serialized_budget_with_context(context=context, budget=budget)
    return serialized


def _normalize_ratio(value: float) -> float:
    return normalize_ratio(value)


def _estimate_tokens(text: str) -> int:
    from npc_engine.retrieval.context_utils import estimate_tokens
    return estimate_tokens(text)
