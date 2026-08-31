"""
context_scoring.py - Relevance scoring helpers for context tier items.
Layer: retrieval
Purpose: Relevance scoring helpers for context tier items.

Does NOT: fetch graph/vector data or enforce token budgets.

Dependencies injected: LLMConfig.
"""

from __future__ import annotations

from typing import Any

from .context_merger import ContextItem
from .context_relevance_engine import ContextRelevanceCandidate, rank_context_candidates
from .context_utils import parse_node_identity
from .context_score_extractors import (
    extract_recency_score,
    extract_relation_score,
    extract_severity_score_for_item,
    infer_proximity_hops,
    payload_for_scoring,
    quest_score,
)
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.world.time_utils import TimePoint


# NPC_SELF_STATE_KEYS and SELF_STATE_PROXIMITY_HOPS now live in context_slots, DERIVED
# from the declaration table, and are consumed by context_score_extractors.infer_proximity_hops.
# They used to be a hand-maintained tuple here, and a key missing from it fell through to
# the max_proximity_hops default -- proximity 0.0, the score of a node at the graph horizon
# -- so an NPC's own beliefs and memories ranked below the strangers standing in the room
# with it (ISSUE-163).


def rank_tier_items(
    *,
    items: list[ContextItem],
    llm_config: LLMConfig,
    vector_scores: dict[str, float],
    trust_scores: dict[str, float] | None = None,
    active_quest: dict[str, Any] | None = None,
    game_time: TimePoint | None = None,
    weight_profile: str | None = None,
    explicit_node_ids: frozenset[str] = frozenset(),
) -> list[ContextItem]:
    """Score and rank context items by relevance.

    Args:
        items: Unordered context items to rank.
        llm_config: LLM configuration providing relevance weights and proximity settings.
        vector_scores: Map of item key to normalized vector similarity score.
        trust_scores: Optional map of Tier A event item key to trust score (0–1). (6.2)
        active_quest: Optional active quest dict for quest-relevance scoring. (6.4)
        game_time: Current structured game time for scoring game-time nodes. (8.2)
        weight_profile: Named weight profile override (e.g. "investigation"). (8.3)
        explicit_node_ids: Node IDs pinned by the game engine as relevant this turn.
            Matching nodes score explicit=1.0; all others score 0.0.

    Returns:
        Items reordered by descending relevance score with updated priority fields.
    """

    resolved_weights = llm_config.resolve_weights(weight_profile or llm_config.default_weight_profile)
    candidates = [
        _build_candidate(
            item=item,
            llm_config=llm_config,
            vector_scores=vector_scores,
            trust_scores=trust_scores,
            active_quest=active_quest,
            game_time=game_time,
            explicit_node_ids=explicit_node_ids,
        )
        for item in items
    ]
    return rank_context_candidates(
        candidates=candidates,
        weights=resolved_weights,
        max_proximity_hops=llm_config.max_proximity_hops,
    )


def _build_candidate(
    *,
    item: ContextItem,
    llm_config: LLMConfig,
    vector_scores: dict[str, float],
    trust_scores: dict[str, float] | None = None,
    active_quest: dict[str, Any] | None = None,
    game_time: TimePoint | None = None,
    explicit_node_ids: frozenset[str] = frozenset(),
) -> ContextRelevanceCandidate:
    node_type, node_id = parse_node_identity(item.key)
    payload = payload_for_scoring(item.text)
    return ContextRelevanceCandidate(
        node_type=node_type,
        node_id=node_id,
        item=item,
        recency=extract_recency_score(payload, game_time=game_time, game_day_horizon=llm_config.recency_game_day_horizon),
        severity=extract_severity_score_for_item(item.key, item.text),
        proximity_hops=infer_proximity_hops(item.key, llm_config.max_proximity_hops),
        relation=extract_relation_score(item=item, vector_scores=vector_scores, trust_scores=trust_scores),
        quest=quest_score(item=item, active_quest=active_quest),
        explicit=1.0 if node_id in explicit_node_ids else 0.0,
    )
