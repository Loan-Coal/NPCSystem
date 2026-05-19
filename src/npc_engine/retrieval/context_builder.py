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

import asyncio
from typing import Protocol

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
from npc_engine.graph.quest_queries import get_active_quest_for_player
from npc_engine.retrieval.context_budget_enforcer import ContextCompressionCache, enforce_context_budget
from npc_engine.retrieval.context_builder_helpers import (
    enforce_final_serialized_budget_with_context,
    expand_query,
    keyword_overlap,
    normalize_ratio,
    rerank_by_keyword,
    to_json_safe,
)
from npc_engine.retrieval.context_merger import ContextItem, MergedContext, merge_context
from npc_engine.retrieval.context_metrics import (
    CONTEXT_BUDGET_ERRORS_METRIC,
    CONTEXT_CACHE_HITS_METRIC,
    CONTEXT_CACHE_MISSES_METRIC,
    record_compression_metrics,
    record_context_metrics,
)
from npc_engine.retrieval.context_scoring import rank_tier_items
from npc_engine.retrieval.context_serializer import serialize_context
from npc_engine.retrieval.context_utils import serialize_json
from npc_engine.retrieval.dialogue_context_cache import DialogueContextCache
from npc_engine.retrieval.subgraph_retriever import assemble_tier_a_context
from npc_engine.retrieval.vector_store_protocol import VectorSearchResult
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.utils.errors import ContextBudgetError
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
    context_cache: DialogueContextCache | None = None,
    session_id: str | None = None,
    skip_rag: bool = False,
    player_id: str | None = None,
) -> str:
    """Build the final serialized prompt context string for one dialogue turn.

    Issues graph queries in 3 parallel asyncio.gather stages, applies relevance
    scoring, budget enforcement, and serializes to compact JSON.

    Raises:
        ValueError: If RAG_TOP_K is not greater than 0.
        ContextBudgetError: If tier A or total prompt budget cannot be satisfied.
    """

    if settings.RAG_TOP_K <= 0:
        raise ValueError("RAG_TOP_K must be greater than 0")

    # Stage 1: fully independent queries — character bundle, world state, known event IDs
    character_bundle, world_state, known_event_ids = await asyncio.gather(
        get_character_with_relations(session=session, npc_id=npc_id),
        get_world_state(session=session),
        get_known_event_ids_for_npc(session=session, npc_id=npc_id),
    )

    character_payload = character_bundle.get("character")
    emotion_snapshot = emotion_state or {"current_mood": "neutral"}
    if emotion_state is None and isinstance(character_payload, dict):
        emotion_snapshot = {
            "current_mood": str(character_payload.get("current_mood", "neutral")),
        }

    cache_key = None
    if context_cache is not None and session_id is not None:
        npc_ts = str(character_payload.get("last_graph_updated_at", "")) if isinstance(character_payload, dict) else ""
        world_ts = world_state.last_updated_at.isoformat() if world_state.last_updated_at else ""
        current_mood = str(emotion_snapshot.get("current_mood", "neutral"))
        cache_key = context_cache.build_key(
            npc_id=npc_id,
            session_id=session_id,
            player_id=player_id or "",
            npc_last_graph_updated_at=npc_ts,
            world_last_updated_at=world_ts,
            current_mood=current_mood,
        )
        cached = context_cache.get(cache_key)
        if cached is not None:
            increment_metric(metric=CONTEXT_CACHE_HITS_METRIC, labels={"npc_id": npc_id})
            return cached
        increment_metric(metric=CONTEXT_CACHE_MISSES_METRIC, labels={"npc_id": npc_id})

    # Stage 2: location_id + optional vector search in parallel.
    #   Vector search uses conversation-expanded query (6.3) filtered to KNOWS_ABOUT events.
    rag_filter = known_event_ids if known_event_ids else None
    rag_query = expand_query(player_message, session_turns)
    if not skip_rag:
        location_id, tier_b_results = await asyncio.gather(
            get_npc_location_id(session=session, npc_id=npc_id),
            embedding_index.search(query=rag_query, top_k=settings.RAG_TOP_K, filter_ids=rag_filter),
        )
    else:
        location_id = await get_npc_location_id(session=session, npc_id=npc_id)
        tier_b_results = []

    # Stage 3: all remaining graph queries in parallel
    (
        location_context,
        events,
        reputation_items,
        memories,
        beliefs,
        goals,
        owned_items,
        secrets,
        obligations,
        group_memberships,
        believed_rumors,
        traits,
        active_pledges,
    ) = await asyncio.gather(
        get_location_context(session=session, location_id=location_id),
        get_events_for_npc(session=session, npc_id=npc_id, limit=settings.RAG_TOP_K),
        get_reputation_context_for_npc(
            session,
            npc_id=npc_id,
            player_id=player_id or "",
            threshold=settings.REPUTATION_CONTEXT_THRESHOLD,
        ),
        get_memories_for_character(session, character_id=npc_id, k=3),
        get_beliefs_for_character(session, character_id=npc_id, k=10),
        get_goals_for_character(session, character_id=npc_id, k=10, status_filter="active"),
        get_items_for_character(session, character_id=npc_id, k=10),
        get_secrets_for_character(session, character_id=npc_id, k=10),
        get_debts_for_character(session, character_id=npc_id, k=5),
        get_groups_for_character_svc(session, character_id=npc_id),
        get_rumors_for_character_svc(session, character_id=npc_id, min_confidence=30),
        get_traits_svc(session, npc_id),
        get_pledges_for_character_svc(session, npc_id, active_only=True),
    )

    # 6.1 Two-pass rerank: fetch top-10 by intrinsic score, keep top-3 by keyword overlap.
    beliefs = rerank_by_keyword(beliefs, "content", player_message, top_k=3)
    goals = rerank_by_keyword(goals, "objective", player_message, top_k=3)
    secrets = rerank_by_keyword(secrets, "content", player_message, top_k=3)

    # Stage 4: trust scores + second-hop events + player quest state (depends on Stage 3).
    event_ids = [str(e["id"]) for e in events if e.get("id")]

    async def _no_quest() -> dict | None:
        return None

    trust_scores, second_hop_events, active_quest = await asyncio.gather(
        get_trust_scores_for_events(session, npc_id=npc_id, event_ids=event_ids),
        get_second_hop_events(session, npc_id=npc_id),
        get_active_quest_for_player(session, player_id=player_id) if player_id else _no_quest(),
    )

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
        reputation_lines = [
            f"Player reputation with {item['faction_name']}: {item['standing']} ({item['label']})"
            for item in reputation_items
        ]
        tier_a_raw.append(
            ContextItem(
                key="reputation",
                text=serialize_json(reputation_lines),
                tier="tierA",
                priority=85,
            )
        )

    if active_quest:
        tier_a_raw.append(ContextItem(key="active_quest", text=serialize_json(active_quest), tier="tierA", priority=89))
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
                text=serialize_json(evt, strip_nulls=True),
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

    tier_a = rank_tier_items(
        items=tier_a_raw,
        llm_config=llm_config,
        vector_scores=vector_scores,
        trust_scores=event_key_trust,
        active_quest=active_quest,
    )
    tier_b = rank_tier_items(items=tier_b_raw, llm_config=llm_config, vector_scores=vector_scores)
    tier_c = rank_tier_items(items=tier_c_raw, llm_config=llm_config, vector_scores=vector_scores)

    merged = merge_context(tier0=tier0, tier_a=tier_a, tier_b=tier_b, tier_c=tier_c)
    try:
        trimmed = enforce_context_budget(
            context=merged,
            llm_config=llm_config,
            compression_cache=compression_cache,
        )
    except ContextBudgetError as error:
        increment_metric(metric=CONTEXT_BUDGET_ERRORS_METRIC, labels={"tier": error.tier})
        raise

    final_context, serialized = enforce_final_serialized_budget_with_context(
        context=trimmed,
        budget=settings.PROMPT_TOKEN_BUDGET,
    )
    record_context_metrics(context=final_context)
    record_compression_metrics(pre_budget_context=merged, post_budget_context=final_context)

    if context_cache is not None and cache_key is not None:
        context_cache.set(cache_key, serialized)

    return serialized


def _to_json_safe(value):
    """Delegate to the helpers module for backward compatibility."""
    return to_json_safe(value)


# Backward-compatibility shims for tests that import these names directly.
def _enforce_final_serialized_budget_with_context(context: MergedContext, budget: int) -> tuple[MergedContext, str]:
    return enforce_final_serialized_budget_with_context(context=context, budget=budget)


def _enforce_final_serialized_budget(context: MergedContext, budget: int) -> str:
    _, serialized = enforce_final_serialized_budget_with_context(context=context, budget=budget)
    return serialized


def _normalize_ratio(value: float) -> float:
    return normalize_ratio(value)


def _estimate_tokens(text: str) -> int:
    from npc_engine.retrieval.context_utils import estimate_tokens
    return estimate_tokens(text)
