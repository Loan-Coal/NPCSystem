"""
Module: context_builder
Layer: retrieval
Purpose: Orchestrates context merge, relevance scoring, budget enforcement, and serialization.
Does NOT: call LLM adapters.
Dependencies injected: EmbeddingIndex.
Used by: engines.dialogue.dialogue_handler

NOTE: This file exceeds the 300-line limit (currently ~448 lines). The public function
build_serialized_context is an async pipeline — every line is part of one cohesive orchestration
flow. Each stage is extracted into a private helper. See DECISIONS.md entry
"context_builder.py exceeds 300-line limit (Phase 6)" for the full analysis.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

from neo4j import AsyncSession

from npc_engine.config import Settings
from npc_engine.graph.graph_reader import (
    get_character_with_relations,
    get_events_for_npc,
    get_known_event_ids_for_npc,
    get_location_context,
    get_npc_location_id,
    get_npc_player_edge,
)
from npc_engine.graph.need_queries import get_needs_for_character
from npc_engine.graph.belief_queries import get_beliefs_for_character
from npc_engine.graph.goal_queries import get_goals_for_character
from npc_engine.graph.item_queries import get_items_for_character
from npc_engine.graph.secret_queries import get_secrets_for_character
from npc_engine.graph.owes_queries import get_debts_for_character
from npc_engine.graph.group.group_service import get_groups_for_character_svc
from npc_engine.graph.rumor_service import get_rumors_for_character_svc
from npc_engine.graph.trait_service import get_traits_svc
from npc_engine.graph.pledge_service import get_pledges_for_character_svc
from npc_engine.graph.memory.memory_queries import (
    get_memories_for_character,
    get_player_memories_for_npc,
)
from npc_engine.graph.reputation_queries import get_reputation_context_for_npc
from npc_engine.graph.trust_queries import get_second_hop_events, get_trust_scores_for_events
from npc_engine.graph.quest_queries import get_active_quest_for_player
from .context_budget_enforcer import ContextCompressionCache, fill_to_budget
from .context_builder_helpers import (
    expand_query,
    normalize_ratio,
    rerank_by_keyword,
    to_json_safe,
)
from .context_merger import ContextItem, MergedContext, merge_context
from npc_engine.retrieval.graph_rag.memory_temporal import annotate_memory_ages
from .context_metrics import (
    CONTEXT_CACHE_HITS_METRIC,
    CONTEXT_CACHE_MISSES_METRIC,
    record_compression_metrics,
    record_context_metrics,
)
from .context_scoring import rank_tier_items
from npc_engine.retrieval.graph_rag.graph_rag import graph_rag_retrieve
from npc_engine.retrieval.embedding.topic_classifier import detect_dialogue_profile
from npc_engine.world.time_utils import TimePoint
from .context_utils import serialize_json
from npc_engine.retrieval.dialogue_context.dialogue_context_cache import DialogueContextCache, PartialDialogueContextCache
from npc_engine.retrieval.graph_rag.subgraph_retriever import assemble_tier_a_context
from npc_engine.retrieval.embedding.vector_store_protocol import VectorSearchResult
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.utils.metrics import increment_metric
from npc_engine.graph.world_state.world_state_reader import get_world_state


from pydantic import BaseModel


# Level below which a need is considered "unmet" and surfaced to dialogue context.
# Needs are modelled on a 0-100 scale; lower = more urgent.
NEED_UNMET_LEVEL_THRESHOLD: int = 50


class NeedSnapshot(BaseModel):
    """Typed snapshot of a single NPC need node — no raw dict crosses module boundary.

    Attributes:
        need_id: Unique node ID in the graph.
        kind:    Semantic kind (e.g. "hunger", "social", "rest").
        level:   Current level on a 0-100 scale.  Lower = more urgent.
        character_id: Owning NPC node ID.
    """

    need_id: str
    kind: str
    level: int
    character_id: str


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


# ---------------------------------------------------------------------------
# Need helpers
# ---------------------------------------------------------------------------

async def _fetch_top_unmet_need(
    session: AsyncSession,
    npc_id: str,
) -> NeedSnapshot | None:
    """Return the most urgent unmet need for an NPC, or None if all needs are met.

    A need is considered unmet when its level is strictly below
    NEED_UNMET_LEVEL_THRESHOLD (0-100 scale; lower = more urgent).  The most
    urgent need is the one with the lowest level.

    Args:
        session:  Active Neo4j async session.
        npc_id:   The NPC whose needs to inspect.

    Returns:
        NeedSnapshot of the highest-urgency unmet need, or None.
    """
    raw_needs = await get_needs_for_character(session=session, character_id=npc_id)
    unmet = [
        n for n in raw_needs
        if isinstance(n.get("level"), (int, float))
        and int(n["level"]) < NEED_UNMET_LEVEL_THRESHOLD
    ]
    if not unmet:
        return None
    most_urgent = min(unmet, key=lambda n: int(n["level"]))
    return NeedSnapshot(
        need_id=str(most_urgent.get("need_id", "")),
        kind=str(most_urgent.get("kind", "unknown")),
        level=int(most_urgent["level"]),
        character_id=npc_id,
    )


# ---------------------------------------------------------------------------
# Private pipeline-stage helpers
# ---------------------------------------------------------------------------

async def _fetch_base_graph_data(session: AsyncSession, npc_id: str) -> tuple[dict[str, Any], Any, Any]:
    """Fetch character bundle, world state, and known event IDs for one NPC."""
    character_bundle = await get_character_with_relations(session=session, npc_id=npc_id)
    world_state = await get_world_state(session=session)
    known_event_ids = await get_known_event_ids_for_npc(session=session, npc_id=npc_id)
    return character_bundle, world_state, known_event_ids


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


def _get_partial_cache_state(context_cache: Any, npc_id: str, npc_ts: str) -> tuple[Any, Any, Any, Any, Any]:
    """Extract partial cache and its keys; record hit/miss metrics when both slots are warm."""
    partial_cache: PartialDialogueContextCache | None = (
        context_cache if isinstance(context_cache, PartialDialogueContextCache) else None
    )
    if partial_cache is None:
        return None, None, None, None, None
    profile_key = partial_cache.build_profile_key(npc_id=npc_id, npc_last_graph_updated_at=npc_ts)
    bg_key = partial_cache.build_beliefs_goals_key(npc_id=npc_id, npc_last_graph_updated_at=npc_ts)
    cached_profile = partial_cache.get_profile(profile_key)
    cached_bg = partial_cache.get_beliefs_goals(bg_key)
    if cached_profile is not None and cached_bg is not None:
        increment_metric(metric=CONTEXT_CACHE_HITS_METRIC, labels={"npc_id": npc_id})
    else:
        increment_metric(metric=CONTEXT_CACHE_MISSES_METRIC, labels={"npc_id": npc_id})
    return partial_cache, profile_key, bg_key, cached_profile, cached_bg


async def _fetch_rag_results(
    session: AsyncSession, embedding_index: EmbeddingIndexProtocol, settings: Settings,
    player_message: str, session_turns: list[str], known_event_ids: set[str] | None,
    npc_id: str, game_time: TimePoint | None, skip_rag: bool,
) -> list[Any]:
    """Run vector-only or GraphRAG retrieval for Tier B/C items; return empty list when skip_rag."""
    if skip_rag:
        return []
    rag_query = expand_query(player_message, session_turns)
    rag_filter = known_event_ids if known_event_ids else None
    if settings.GRAPH_RAG_ENABLED:
        return await graph_rag_retrieve(
            session=session, embedding_index=embedding_index, query=rag_query,
            npc_id=npc_id, known_event_ids=known_event_ids or set(), top_k=settings.RAG_TOP_K, game_time=game_time,
        )
    return await embedding_index.search(query=rag_query, top_k=settings.RAG_TOP_K, filter_ids=rag_filter)


async def _fetch_npc_profile_data(
    session: AsyncSession, npc_id: str, settings: Settings,
    player_id: str | None, location_id: str | None,
) -> tuple[Any, ...]:
    """Fetch NPC profile: location, events, reputation, memories, items, groups, rumors, traits, pledges."""
    location_context = await get_location_context(session=session, location_id=location_id or "")
    events = await get_events_for_npc(session=session, npc_id=npc_id, limit=settings.RAG_TOP_K)
    reputation_items = await get_reputation_context_for_npc(
        session, npc_id=npc_id, player_id=player_id or "", threshold=settings.REPUTATION_CONTEXT_THRESHOLD,
    )
    memories = await get_memories_for_character(session, character_id=npc_id, k=3)
    owned_items = await get_items_for_character(session, character_id=npc_id, k=10)
    group_memberships = await get_groups_for_character_svc(session, character_id=npc_id)
    believed_rumors = await get_rumors_for_character_svc(session, character_id=npc_id, min_confidence=30)
    traits = await get_traits_svc(session, npc_id)
    active_pledges = await get_pledges_for_character_svc(session, npc_id, active_only=True)
    return (location_context, events, reputation_items, memories, owned_items, group_memberships, believed_rumors, traits, active_pledges)


async def _fetch_beliefs_goals_data(session: AsyncSession, npc_id: str) -> tuple[Any, ...]:
    """Fetch NPC beliefs, active goals, secrets, and obligations."""
    beliefs = await get_beliefs_for_character(session, character_id=npc_id, k=10)
    goals = await get_goals_for_character(session, character_id=npc_id, k=10, status_filter="active")
    secrets = await get_secrets_for_character(session, character_id=npc_id, k=10)
    obligations = await get_debts_for_character(session, character_id=npc_id, k=5)
    return beliefs, goals, secrets, obligations


async def _resolve_npc_context_with_cache(
    session: AsyncSession, npc_id: str, settings: Settings, player_id: str | None,
    location_id: str | None, partial_cache: Any, profile_key: Any, bg_key: Any,
    cached_profile: Any, cached_bg: Any,
    player_message: str,
) -> tuple[Any, Any, Any, Any, Any]:
    """Fetch or restore profile+beliefs/goals with partial cache; return (profile_data, beliefs, goals, secrets, obligations)."""
    profile_miss = cached_profile is None
    bg_miss = cached_bg is None
    if profile_miss and bg_miss:
        new_profile = await _fetch_npc_profile_data(session, npc_id, settings, player_id, location_id)
        new_bg = await _fetch_beliefs_goals_data(session, npc_id)
    elif profile_miss:
        new_profile = await _fetch_npc_profile_data(session, npc_id, settings, player_id, location_id)
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


async def _fetch_player_data(
    session: AsyncSession, npc_id: str, player_id: str | None, events: list[Any],
) -> tuple[Any, ...]:
    """Fetch trust scores, second-hop events, active quest, and player relation edge."""
    event_ids = [str(e["id"]) for e in events if e.get("id")]
    trust_scores = await get_trust_scores_for_events(session, npc_id=npc_id, event_ids=event_ids)
    second_hop_events = await get_second_hop_events(session, npc_id=npc_id)
    active_quest = await get_active_quest_for_player(session, player_id=player_id) if player_id else None
    player_relation_edge: dict[str, Any] | None = None
    if player_id:
        player_relation_edge = await get_npc_player_edge(session, npc_id=npc_id, player_id=player_id)
    return trust_scores, second_hop_events, active_quest, player_relation_edge


async def _maybe_cross_encode(settings: Settings, player_message: str, tier_b_results: list[Any]) -> list[Any]:
    """Apply cross-encoder reranking if CROSS_ENCODER_ENABLED and results are non-empty.

    The rerank does synchronous sentence-transformers inference, so it is offloaded
    to a worker thread (asyncio.to_thread) to keep the event loop unblocked (ISSUE-064,
    mirroring the ISSUE-063 embedding-index fix).
    """
    if not (settings.CROSS_ENCODER_ENABLED and tier_b_results):
        return tier_b_results
    from npc_engine.retrieval.embedding import cross_encoder_reranker
    reranked = await asyncio.to_thread(cross_encoder_reranker.rerank, player_message, tier_b_results)
    return list(reranked)


def _build_tier0_items(
    world_state: Any,
    emotion_snapshot: dict[str, Any],
    system_state_context: Any | None = None,
) -> list[ContextItem]:
    """Build pinned Tier 0 context items: world state, current emotion, and system state.

    Args:
        world_state: Authoritative world state from the graph.
        emotion_snapshot: Current NPC emotion snapshot dict.
        system_state_context: Optional engine-resolved SystemStateContext (ISSUE-071).
    """
    items = [
        ContextItem(key="world", text=world_state.model_dump_json(), tier="tier0", priority=100, pinned=True),
        ContextItem(key="emotion", text=serialize_json(emotion_snapshot), tier="tier0", priority=95, pinned=True),
    ]
    if system_state_context is not None:
        items.append(
            ContextItem(
                key="system_state",
                text=system_state_context.model_dump_json(),
                tier="tier0",
                priority=97,
                pinned=True,
            )
        )
    return items


def _build_tier_a_base(
    npc_id: str, character_bundle: dict[str, Any], events: list[Any], location_id: str | None,
    location_context: Any, group_memberships: list[Any], believed_rumors: list[Any],
    traits: list[Any], active_pledges: list[Any], session_turns: list[str],
) -> list[ContextItem]:
    """Build base Tier A items: session turns followed by NPC character profile section."""
    items = [ContextItem(key="session", text=serialize_json(session_turns), tier="tierA", priority=99, pinned=True)]
    items.extend(assemble_tier_a_context(
        npc_id=npc_id, character_bundle=character_bundle, events=events, location_id=location_id,
        location_context=location_context, group_memberships=group_memberships or [],
        believed_rumors=believed_rumors or [], traits=traits or [], active_pledges=active_pledges or [],
    ))
    return items


def _build_tier_a_extended(
    player_id: str | None, reputation_items: list[Any], active_quest: Any,
    player_relation_edge: dict[str, Any] | None,
    memories: list[Any], beliefs: list[Any], goals: list[Any], owned_items: list[Any],
    secrets: list[Any], obligations: list[Any],
    second_hop_events: list[Any], settings: Settings, npc_id: str, game_time: TimePoint | None = None,
) -> list[ContextItem]:
    """Build extended Tier A items: reputation, quest, beliefs, memories, second-hop events, etc."""
    items: list[Any] = []
    if player_id and reputation_items:
        items.append(ContextItem(key="reputation", text=serialize_json(reputation_items), tier="tierA", priority=85))
    if active_quest:
        items.append(ContextItem(key="active_quest", text=serialize_json(active_quest), tier="tierA", priority=89, pinned=True))
    if player_relation_edge is not None:
        # ISSUE-070: subgraph_retriever also emits key="relation:player" (priority=95). merge_context dedups
        # by key keeping the higher priority, so the subgraph item wins deterministically when both are
        # present; this 88 applies only when subgraph_retriever produced no relation edge.
        items.append(ContextItem(key="relation:player", text=serialize_json(player_relation_edge), tier="tierA", priority=88))
    if memories:
        aged_memories = annotate_memory_ages(memories, game_time)
        items.append(ContextItem(key="memories", text=serialize_json(aged_memories), tier="tierA", priority=90))
    if beliefs:
        items.append(ContextItem(key="beliefs", text=serialize_json(beliefs), tier="tierA", priority=88))
    if goals:
        items.append(ContextItem(key="goals", text=serialize_json(goals), tier="tierA", priority=87))
    if owned_items:
        items.append(ContextItem(key="owned_items", text=serialize_json(owned_items), tier="tierA", priority=86))
    if secrets:
        items.append(ContextItem(key="secrets", text=serialize_json(secrets), tier="tierA", priority=84))
    if obligations:
        items.append(ContextItem(key="obligations", text=serialize_json(obligations), tier="tierA", priority=83))
    for idx, evt in enumerate((second_hop_events or [])[:settings.MAX_SECOND_HOP_EVENTS]):
        items.append(ContextItem(key=f"second_hop:{idx}:{npc_id}", text=serialize_json(evt, strip_nulls=True), tier="tierA", priority=74 - idx))
    return items


def _build_tier_b_c_items(tier_b_results: list[Any]) -> tuple[Any, ...]:
    """Split RAG results into Tier B/C ContextItems and build a vector score map."""
    tier_b_raw: list[Any] = []
    tier_c_raw: list[Any] = []
    vector_scores: dict[str, float] = {}
    if not tier_b_results:
        return tier_b_raw, tier_c_raw, vector_scores
    split_index = max(1, len(tier_b_results) // 2)
    for index, row in enumerate(tier_b_results):
        item = ContextItem(
            key=f"rag:{row['id']}",
            text=serialize_json(_to_json_safe(row["payload"])),
            tier="tierB" if index < split_index else "tierC",
            priority=max(1, 60 - index),
        )
        (tier_b_raw if item.tier == "tierB" else tier_c_raw).append(item)
    vector_scores = {f"rag:{row['id']}": normalize_ratio(float(row.get("score", 0.0))) for row in tier_b_results}
    return tier_b_raw, tier_c_raw, vector_scores


def _build_event_trust_map(events: list[Any], trust_scores: dict[str, Any], npc_id: str) -> dict[str, float]:
    """Map event ContextItem keys (positional index) to their trust scores."""
    event_key_trust: dict[str, float] = {}
    for idx, evt in enumerate(events):
        eid = str(evt.get("id", ""))
        if eid in trust_scores:
            event_key_trust[f"event:{idx}:{npc_id}"] = trust_scores[eid]
    return event_key_trust


def _rank_and_serialize_tiers(
    tier0: list[ContextItem], tier_a_raw: list[ContextItem], tier_b_raw: list[ContextItem],
    tier_c_raw: list[ContextItem],
    vector_scores: dict[str, float], event_key_trust: dict[str, float], llm_config: LLMConfig,
    settings: Settings, compression_cache: Any, weight_profile: str, active_quest: Any,
    game_time: TimePoint | None, explicit_node_ids: frozenset[str],
) -> str:
    """Rank all tiers, merge, enforce budget, record metrics, and serialize to JSON string."""
    tier_a = rank_tier_items(items=tier_a_raw, llm_config=llm_config, vector_scores=vector_scores,
                             trust_scores=event_key_trust, active_quest=active_quest, game_time=game_time,
                             weight_profile=weight_profile, explicit_node_ids=explicit_node_ids)
    tier_b = rank_tier_items(items=tier_b_raw, llm_config=llm_config, vector_scores=vector_scores,
                             game_time=game_time, weight_profile=weight_profile, explicit_node_ids=explicit_node_ids)
    tier_c = rank_tier_items(items=tier_c_raw, llm_config=llm_config, vector_scores=vector_scores,
                             game_time=game_time, weight_profile=weight_profile, explicit_node_ids=explicit_node_ids)
    merged = merge_context(tier0=tier0, tier_a=tier_a, tier_b=tier_b, tier_c=tier_c)
    final_context, serialized = fill_to_budget(
        context=merged, llm_config=llm_config,
        prompt_token_budget=settings.PROMPT_TOKEN_BUDGET, compression_cache=compression_cache,
    )
    record_context_metrics(context=final_context)
    record_compression_metrics(pre_budget_context=merged, post_budget_context=final_context)
    return str(serialized)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_TOP_NEED_TIER_B_PRIORITY = 55


async def _fetch_player_memory_item(
    session: AsyncSession,
    npc_id: str,
    player_id: str | None,
    game_time: TimePoint | None,
) -> ContextItem | None:
    """Fetch player-scoped memories and return a Tier-A ContextItem, or None.

    Only executes the graph read when ``player_id`` is non-None.  Results are
    annotated with temporal age metadata before serialization.

    Args:
        session: Active Neo4j async session.
        npc_id: ID of the NPC whose memories to query.
        player_id: ID of the player for whom to filter memories.  When None
            the function returns None immediately (no graph call).
        game_time: Current game-time snapshot used for age annotation.

    Returns:
        A ContextItem keyed ``"player_memories"`` when the NPC holds memories
        for that player; None otherwise.
    """
    if not player_id:
        return None
    raw = await get_player_memories_for_npc(session, npc_id=npc_id, player_id=player_id, k=5)
    if not raw:
        return None
    aged = annotate_memory_ages(raw, game_time)
    return ContextItem(key="player_memories", text=serialize_json(aged), tier="tierA", priority=91)


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


async def build_serialized_context(
    session: AsyncSession, settings: Settings, llm_config: LLMConfig, embedding_index: EmbeddingIndexProtocol,
    npc_id: str, player_message: str, session_turns: list[str], emotion_state: dict[str, Any] | None = None,
    compression_cache: ContextCompressionCache | None = None,
    context_cache: PartialDialogueContextCache | DialogueContextCache | None = None,
    session_id: str | None = None, skip_rag: bool = False, player_id: str | None = None,
    weight_profile: str | None = None, explicit_node_ids: frozenset[str] = frozenset(),
    system_state_context: Any | None = None,
) -> str:
    """Build the final serialized prompt context string for one dialogue turn (raises ValueError if RAG_TOP_K <= 0)."""
    if settings.RAG_TOP_K <= 0:
        raise ValueError("RAG_TOP_K must be greater than 0")
    character_bundle, world_state, known_event_ids = await _fetch_base_graph_data(session, npc_id)
    emotion_snapshot, current_game_time, npc_ts, world_ts = _resolve_initial_state(character_bundle, emotion_state, world_state)
    cache_hit, legacy_cache, legacy_key = _check_legacy_cache(context_cache, session_id, npc_id, player_id, emotion_snapshot, npc_ts, world_ts)
    if cache_hit is not None:
        return str(cache_hit)
    partial_cache, profile_key, bg_key, cached_profile, cached_bg = _get_partial_cache_state(context_cache, npc_id, npc_ts)
    location_id = await get_npc_location_id(session=session, npc_id=npc_id)
    tier_b_results = await _fetch_rag_results(session, embedding_index, settings, player_message, session_turns, known_event_ids, npc_id, current_game_time, skip_rag)
    profile_data, beliefs, goals, secrets, obligations = await _resolve_npc_context_with_cache(session, npc_id, settings, player_id, location_id, partial_cache, profile_key, bg_key, cached_profile, cached_bg, player_message)
    location_context, events, reputation_items, memories, owned_items, group_memberships, believed_rumors, traits, active_pledges = profile_data
    trust_scores, second_hop_events, active_quest, player_relation_edge = await _fetch_player_data(session, npc_id, player_id, events)
    tier_b_results = await _maybe_cross_encode(settings, player_message, tier_b_results)
    tier0 = _build_tier0_items(world_state, emotion_snapshot, system_state_context)
    tier_a_raw = _build_tier_a_base(npc_id, character_bundle, events, location_id, location_context, group_memberships, believed_rumors, traits, active_pledges, session_turns)
    tier_a_raw.extend(_build_tier_a_extended(player_id, reputation_items, active_quest, player_relation_edge, memories, beliefs, goals, owned_items, secrets, obligations, second_hop_events, settings, npc_id, current_game_time))
    await _maybe_append_player_memory(session, npc_id, player_id, current_game_time, tier_a_raw)
    tier_b_raw, tier_c_raw, vector_scores = _build_tier_b_c_items(tier_b_results)
    tier_b_raw = await _maybe_append_top_need(session, npc_id, tier_b_raw)
    event_key_trust = _build_event_trust_map(events, trust_scores, npc_id)
    serialized = _rank_and_serialize_tiers(
        tier0=tier0, tier_a_raw=tier_a_raw, tier_b_raw=tier_b_raw, tier_c_raw=tier_c_raw,
        vector_scores=vector_scores, event_key_trust=event_key_trust, llm_config=llm_config,
        settings=settings, compression_cache=compression_cache, weight_profile=weight_profile or detect_dialogue_profile(player_message),
        active_quest=active_quest, game_time=current_game_time, explicit_node_ids=explicit_node_ids,
    )
    if legacy_cache is not None and legacy_key is not None:
        legacy_cache.set(legacy_key, serialized)
    return serialized


def _to_json_safe(value: Any) -> Any:
    """Delegate to the helpers module for backward compatibility."""
    return to_json_safe(value)


# Backward-compatibility shims for tests that import these names directly.
def _enforce_final_serialized_budget_with_context(context: MergedContext, budget: int) -> tuple[MergedContext, str]:
    from .context_builder_helpers import enforce_final_serialized_budget_with_context
    return enforce_final_serialized_budget_with_context(context=context, budget=budget)


def _enforce_final_serialized_budget(context: MergedContext, budget: int) -> str:
    from .context_builder_helpers import enforce_final_serialized_budget_with_context
    _, serialized = enforce_final_serialized_budget_with_context(context=context, budget=budget)
    return serialized


def _normalize_ratio(value: float) -> float:
    return normalize_ratio(value)


def _estimate_tokens(text: str) -> int:
    from .context_utils import estimate_tokens
    return estimate_tokens(text)
