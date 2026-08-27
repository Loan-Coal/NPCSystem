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
from npc_engine.graph.needs_goals.need_queries import get_needs_for_character
from npc_engine.graph.knowledge.belief_queries import get_beliefs_for_character
from npc_engine.graph.needs_goals.goal_queries import get_goals_for_character
from npc_engine.graph.economy.item_queries import get_items_for_character
from npc_engine.graph.intrigue.secret_queries import get_secrets_for_character
from npc_engine.graph.economy.owes_queries import get_debts_for_character
from npc_engine.graph.group.group_service import get_groups_for_character_svc
from npc_engine.graph.gossip.rumor_service import get_rumors_for_character_svc
from npc_engine.graph.character.trait_service import get_traits_svc
from npc_engine.graph.political.pledge_service import get_pledges_for_character_svc
from npc_engine.graph.memory.memory_queries import (
    get_memories_for_character,
    get_player_memories_for_npc,
)
from npc_engine.graph.reputation.reputation_queries import (
    get_propagated_reputation_for_npc,
    get_reputation_context_for_npc,
)
from npc_engine.graph.relations.trust_queries import get_second_hop_events, get_trust_scores_for_events
from npc_engine.graph.quest.quest_queries import get_active_quest_for_player
from npc_engine.schema.npc_profile_data_models import NpcProfileData
from npc_engine.schema.retrieval_profile_models import RetrievalProfile

from .context_budget_enforcer import ContextCompressionCache, fill_to_budget_with_report
from .context_profile_resolver import resolve_profile_for_turn, resolved_profile_name
from .context_receipt import ContextReceipt, build_context_receipt
from .context_profile_policy import apply_slot_policy, tier_enabled
from .context_slots import slot_for_key
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
    record_attributed_drop_metrics,
)
from .context_scoring import rank_tier_items
from npc_engine.graph.graph_rag_queries import get_rag_scope_ids_for_npc
from npc_engine.retrieval.graph_rag.graph_rag import graph_rag_retrieve
from npc_engine.retrieval.embedding.topic_classifier import detect_dialogue_profile
from npc_engine.world.time_utils import TimePoint
from .context_utils import NON_PROMPT_NODE_FIELDS, serialize_json
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


async def _fetch_rag_results(
    session: AsyncSession, embedding_index: EmbeddingIndexProtocol, settings: Settings,
    player_message: str, session_turns: list[str], known_event_ids: set[str] | None,
    npc_id: str, game_time: TimePoint | None, skip_rag: bool, profile: RetrievalProfile,
) -> list[Any]:
    """Run vector-only or GraphRAG retrieval for Tier B/C items; return empty when out of scope.

    Graph and vector top-k come from the profile as SEPARATE fields. They were one
    Settings.RAG_TOP_K, which also governed event fetching, so a top-k experiment silently
    changed three things at once and no effect could be attributed to any of them.

    The candidate set is a SCOPE, not a whitelist (DEC-209). It was
    `known_event_ids if known_event_ids else None`, and both branches were wrong in
    opposite directions: the first restricted tier B to events the NPC already carries as
    tier-A `event:` items, making the tier redundant by construction and charging every
    hit twice; the second gave an empty set the run of the whole store, and 7 of 22 NPCs
    in the eval world know zero events. The scope is the NPC's 1-hop subgraph, location
    and faction MINUS its known events. An empty scope means no RAG, never all of it.
    """
    if skip_rag or profile.skip_rag:
        return []
    if not tier_enabled(profile, "tierB") and not tier_enabled(profile, "tierC"):
        return []
    rag_scope = await get_rag_scope_ids_for_npc(session, npc_id=npc_id) - (known_event_ids or set())
    if not rag_scope:
        return []
    rag_query = expand_query(player_message, session_turns)
    if settings.GRAPH_RAG_ENABLED:
        return await graph_rag_retrieve(
            session=session, embedding_index=embedding_index, query=rag_query,
            npc_id=npc_id, scope_ids=rag_scope,
            top_k=profile.graph_rag_top_k, game_time=game_time,
        )
    return await embedding_index.search(query=rag_query, top_k=profile.rag_top_k, filter_ids=rag_scope)


async def _fetch_npc_profile_data(
    session: AsyncSession, npc_id: str, settings: Settings,
    player_id: str | None, location_id: str | None, profile: RetrievalProfile,
) -> NpcProfileData:
    """Fetch NPC profile: location, events, reputation, memories, items, groups, rumors, traits, pledges.

    Returns a named model rather than the 9-tuple this used to be: the tuple was unpacked
    positionally 300 lines away and cached anonymously, so adding a read meant editing both
    ends in lockstep and getting the order wrong was a silent mis-assignment.

    `events_limit` is a distinct profile field, not a RAG top-k, despite having shared
    Settings.RAG_TOP_K with vector and graph retrieval until this split.
    """
    return NpcProfileData(
        location_context=await get_location_context(session=session, location_id=location_id or ""),
        events=await get_events_for_npc(session=session, npc_id=npc_id, limit=profile.events_limit),
        reputation_items=await get_reputation_context_for_npc(
            session, npc_id=npc_id, player_id=player_id or "",
            threshold=settings.REPUTATION_CONTEXT_THRESHOLD,
        ),
        memories=await get_memories_for_character(session, character_id=npc_id, k=3),
        owned_items=await get_items_for_character(session, character_id=npc_id, k=10),
        group_memberships=await get_groups_for_character_svc(session, character_id=npc_id),
        believed_rumors=await get_rumors_for_character_svc(session, character_id=npc_id, min_confidence=30),
        traits=await get_traits_svc(session, npc_id),
        active_pledges=await get_pledges_for_character_svc(session, npc_id, active_only=True),
    )


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


async def _fetch_player_data(
    session: AsyncSession, npc_id: str, player_id: str | None, events: list[Any],
) -> tuple[Any, ...]:
    """Fetch trust scores, second-hop events, active quest, relation edge, propagated rep.

    All four player-scoped reads are skipped entirely on an anonymous turn: with no
    player there is no relation, no quest and no reputation to propagate, so issuing the
    round trips would buy nothing.
    """
    event_ids = [str(e["id"]) for e in events if e.get("id")]
    trust_scores = await get_trust_scores_for_events(session, npc_id=npc_id, event_ids=event_ids)
    second_hop_events = await get_second_hop_events(session, npc_id=npc_id)
    if not player_id:
        return trust_scores, second_hop_events, None, None, []
    active_quest = await get_active_quest_for_player(session, player_id=player_id)
    player_relation_edge = await get_npc_player_edge(session, npc_id=npc_id, player_id=player_id)
    propagated_reputation = await get_propagated_reputation_for_npc(
        session, npc_id=npc_id, player_id=player_id
    )
    return trust_scores, second_hop_events, active_quest, player_relation_edge, propagated_reputation


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


def _build_tier0_items(
    world_state: Any,
    emotion_snapshot: dict[str, Any],
    system_state_context: Any | None = None,
) -> list[ContextItem]:
    """Build pinned Tier 0 context items: world state, current emotion, and system state.

    Every item here is pinned into every prompt, so each is serialized through
    NON_PROMPT_NODE_FIELDS. These previously used raw model_dump_json(), which put
    `world.last_updated_at` — a wall-clock value — into every prompt the engine built
    (EVAL-P20.0 / DEC-176).

    Args:
        world_state: Authoritative world state from the graph.
        emotion_snapshot: Current NPC emotion snapshot dict.
        system_state_context: Optional engine-resolved SystemStateContext (ISSUE-071).
    """
    items = [
        _pinned_tier0_item(key="world", payload=world_state.model_dump(mode="json"), priority=100),
        _pinned_tier0_item(key="emotion", payload=emotion_snapshot, priority=95),
    ]
    if system_state_context is not None:
        items.append(
            _pinned_tier0_item(
                key="system_state",
                payload=system_state_context.model_dump(mode="json"),
                priority=97,
            )
        )
    return items


def _pinned_tier0_item(*, key: str, payload: Any, priority: int) -> ContextItem:
    """Serialize a Tier 0 payload with wall-clock fields stripped (DEC-176)."""
    return ContextItem(
        key=key,
        text=serialize_json(payload, strip_fields=NON_PROMPT_NODE_FIELDS),
        tier="tier0",
        priority=priority,
        pinned=True,
    )


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
    propagated_reputation: list[Any] | None = None,
) -> list[ContextItem]:
    """Build extended Tier A items: reputation, quest, beliefs, memories, second-hop events, etc."""
    items: list[Any] = []
    if player_id and reputation_items:
        items.append(ContextItem(key="reputation", text=serialize_json(reputation_items, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=85))
    # Ranks just below direct reputation on purpose: system_v1.yaml Rule 13 says to apply
    # word-of-mouth reputation ONLY where Rule 2's direct reputation has no entry.
    if player_id and propagated_reputation:
        items.append(ContextItem(key="propagated_reputation", text=serialize_json(propagated_reputation, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=84))
    if active_quest:
        items.append(ContextItem(key="active_quest", text=serialize_json(active_quest, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=89, pinned=True))
    if player_relation_edge is not None:
        # ISSUE-070: subgraph_retriever also emits key="relation:player" (priority=95). merge_context dedups
        # by key keeping the higher priority, so the subgraph item wins deterministically when both are
        # present; this 88 applies only when subgraph_retriever produced no relation edge.
        items.append(ContextItem(key="relation:player", text=serialize_json(player_relation_edge, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=88))
    if memories:
        aged_memories = annotate_memory_ages(memories, game_time)
        items.append(ContextItem(key="memories", text=serialize_json(aged_memories, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=90))
    if beliefs:
        items.append(ContextItem(key="beliefs", text=serialize_json(beliefs, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=88))
    if goals:
        items.append(ContextItem(key="goals", text=serialize_json(goals, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=87))
    if owned_items:
        items.append(ContextItem(key="owned_items", text=serialize_json(owned_items, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=86))
    if secrets:
        items.append(ContextItem(key="secrets", text=serialize_json(secrets, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=84))
    if obligations:
        items.append(ContextItem(key="obligations", text=serialize_json(obligations, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=83))
    for idx, evt in enumerate((second_hop_events or [])[:settings.MAX_SECOND_HOP_EVENTS]):
        items.append(ContextItem(key=f"second_hop:{idx}:{npc_id}", text=serialize_json(evt, strip_nulls=True, strip_fields=NON_PROMPT_NODE_FIELDS), tier="tierA", priority=74 - idx))
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
            text=serialize_json(_to_json_safe(row["payload"]), strip_fields=NON_PROMPT_NODE_FIELDS),
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


def _drop_withheld_items(items: list[ContextItem]) -> list[ContextItem]:
    """Remove items whose declared slot the serializer will not emit.

    ISSUE-200's cost was not the missing serializer lines, it was that the keys were
    produced, ranked and CHARGED to the prompt budget before being discarded -- roughly
    110 tokens a turn bought and never delivered, while items that would have reached the
    model were dropped for want of room.

    Central on purpose. There are four producer modules and twenty-odd call sites; a check
    inside each producer is what gets forgotten at the twenty-first, which is how ISSUE-200
    happened in the first place.

    Fails OPEN: a key no slot declares is kept, because dropping it would hide in production
    exactly the defect `test_context_slot_contract` exists to surface in CI.

    Args:
        items: Raw context items from the producers, in production order.
    Returns:
        The same items, in the same order, minus those whose slot is withheld.
    """
    kept: list[ContextItem] = []
    for item in items:
        slot = slot_for_key(item.key)
        if slot is not None and not slot.default_enabled:
            continue
        kept.append(item)
    return kept


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
