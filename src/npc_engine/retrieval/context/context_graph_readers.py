"""
Module: context_graph_readers
Layer: retrieval
Purpose: Read-only graph and RAG fetches that source raw material for dialogue context tiers.
Does NOT: rank, score, budget or serialize context; no writes and no LLM calls.
Dependencies: graph readers/services, retrieval.graph_rag, context_need_models, context_builder_helpers.
Dependencies injected: AsyncSession, Settings, EmbeddingIndexProtocol (per call).
Used by: retrieval.context.context_builder
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession

from npc_engine.config import Settings
from npc_engine.graph.character.trait_service import get_traits_svc
from npc_engine.graph.economy.item_queries import get_items_for_character
from npc_engine.graph.economy.owes_queries import get_debts_for_character
from npc_engine.graph.gossip.rumor_service import get_rumors_for_character_svc
from npc_engine.graph.graph_rag_queries import get_rag_scope_ids_for_npc
from npc_engine.graph.graph_reader import (
    get_character_with_relations,
    get_events_for_npc,
    get_known_event_ids_for_npc,
    get_location_context,
    get_npc_player_edge,
)
from npc_engine.graph.group.group_service import get_groups_for_character_svc
from npc_engine.graph.intrigue.secret_queries import get_secrets_for_character
from npc_engine.graph.knowledge.belief_queries import get_beliefs_for_character
from npc_engine.graph.memory.memory_queries import (
    get_memories_for_character,
    get_player_memories_for_npc,
)
from npc_engine.graph.needs_goals.goal_queries import get_goals_for_character
from npc_engine.graph.needs_goals.need_queries import get_needs_for_character
from npc_engine.graph.political.pledge_service import get_pledges_for_character_svc
from npc_engine.graph.quest.quest_queries import get_active_quest_for_player
from npc_engine.graph.relations.trust_queries import get_second_hop_events, get_trust_scores_for_events
from npc_engine.graph.reputation.reputation_queries import (
    get_propagated_reputation_for_npc,
    get_reputation_context_for_npc,
)
from npc_engine.graph.world_state.world_state_reader import get_world_state
from npc_engine.retrieval.graph_rag.graph_rag import graph_rag_retrieve
from npc_engine.retrieval.graph_rag.memory_temporal import annotate_memory_ages
from npc_engine.schema.npc_profile_data_models import NpcProfileData
from npc_engine.schema.retrieval_profile_models import RetrievalProfile
from npc_engine.world.time_utils import TimePoint

from .context_builder_helpers import expand_query
from .context_merger import ContextItem
from .context_need_models import NEED_UNMET_LEVEL_THRESHOLD, NeedSnapshot
from .context_profile_policy import tier_enabled
from .context_protocols import EmbeddingIndexProtocol
from .context_utils import serialize_json


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
async def _fetch_base_graph_data(session: AsyncSession, npc_id: str) -> tuple[dict[str, Any], Any, Any]:
    """Fetch character bundle, world state, and known event IDs for one NPC."""
    character_bundle = await get_character_with_relations(session=session, npc_id=npc_id)
    world_state = await get_world_state(session=session)
    known_event_ids = await get_known_event_ids_for_npc(session=session, npc_id=npc_id)
    return character_bundle, world_state, known_event_ids
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
