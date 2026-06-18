"""
context_scoring.py - Relevance scoring helpers for context tier items.
Layer: retrieval
Purpose: (auto-detected — review)

Does NOT: fetch graph/vector data or enforce token budgets.

Dependencies injected: LLMConfig.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from npc_engine.common.json_utils import parse_json_object
from npc_engine.retrieval.context_merger import ContextItem
from npc_engine.retrieval.context_relevance_engine import ContextRelevanceCandidate, rank_context_candidates
from npc_engine.retrieval.context_utils import parse_node_identity
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.world.time_utils import TimePoint, total_days


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
    payload = parse_json_object(item.text)
    return ContextRelevanceCandidate(
        node_type=node_type,
        node_id=node_id,
        item=item,
        recency=_extract_recency_score(payload, game_time=game_time, game_day_horizon=llm_config.recency_game_day_horizon),
        severity=_extract_severity_score(payload),
        proximity_hops=_infer_proximity_hops(item.key, llm_config.max_proximity_hops),
        relation=_extract_relation_score(item=item, vector_scores=vector_scores, trust_scores=trust_scores),
        quest=_quest_score(item=item, active_quest=active_quest),
        explicit=1.0 if node_id in explicit_node_ids else 0.0,
    )


def _extract_recency_score(
    payload: dict[str, Any],
    *,
    game_time: TimePoint | None = None,
    game_day_horizon: int = 365,
) -> float:
    # Game-time nodes (Belief, Goal, Memory): score against current structured game time.
    raw_game_time = payload.get("created_at_game_time") or payload.get("occurred_at_game_time")
    if raw_game_time is not None and game_time is not None:
        try:
            gt = json.loads(raw_game_time) if isinstance(raw_game_time, str) else raw_game_time
            node_tp = TimePoint(
                year=int(gt.get("year", 0)),
                season=str(gt.get("season", "spring")),
                day=int(gt.get("day", 1)),
                time_of_day=str(gt.get("time_of_day", "morning")),
            )
            age_days = max(0, total_days(game_time) - total_days(node_tp))
            return _normalize_ratio(1.0 - min(age_days / game_day_horizon, 1.0))
        except (KeyError, TypeError, ValueError):
            return 0.0

    # Wall-clock nodes (Event, etc.): score by ISO timestamp fields.
    for field in ("occurred_at", "updated_at", "last_graph_updated_at", "created_at"):
        raw_value = payload.get(field)
        if not isinstance(raw_value, str):
            continue
        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age_hours = max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600.0)
        return _normalize_ratio(1.0 - min(age_hours / 72.0, 1.0))
    return 0.0


def _extract_severity_score(payload: dict[str, Any]) -> float:
    # Direct severity field (Event, Secret)
    raw = payload.get("severity")
    if isinstance(raw, (int, float)):
        return _normalize_ratio(float(raw) / 100.0)

    # Goal urgency (0–100)
    urgency = payload.get("urgency")
    if isinstance(urgency, (int, float)):
        return _normalize_ratio(float(urgency) / 100.0)

    # Belief confidence (0–100)
    confidence = payload.get("confidence")
    if isinstance(confidence, (int, float)):
        return _normalize_ratio(float(confidence) / 100.0)

    # Memory emotional charge (-100 to 100) — use absolute value
    charge = payload.get("emotional_charge")
    if isinstance(charge, (int, float)):
        return _normalize_ratio(abs(float(charge)) / 100.0)

    return 0.0


def _extract_relation_score(
    *,
    item: ContextItem,
    vector_scores: dict[str, float],
    trust_scores: dict[str, float] | None = None,
) -> float:
    if item.tier == "tierB":
        return vector_scores.get(item.key, 0.0)
    priority_score = _normalize_ratio(item.priority / 100.0)
    # 6.2: blend priority with trust toward the event's actor when available.
    if trust_scores and item.key.startswith("event:"):
        trust = trust_scores.get(item.key)
        if trust is not None:
            return 0.5 * priority_score + 0.5 * trust
    return priority_score


def _quest_score(*, item: ContextItem, active_quest: dict[str, Any] | None = None) -> float:
    if "quest" in item.key.lower():
        return 1.0
    # 6.4: boost items whose payload references the active quest's target or giver.
    if active_quest is not None:
        ids_to_match = {active_quest.get("target_id"), active_quest.get("giver_id")} - {None}
        if ids_to_match:
            payload = parse_json_object(item.text)
            if any(str(v) in ids_to_match for v in payload.values() if isinstance(v, str)):
                return 1.0
    return 0.0


def _infer_proximity_hops(key: str, max_proximity_hops: int) -> int:
    lowered = key.lower()
    if lowered.startswith("character:") or lowered.startswith("relation:"):
        return 0
    if lowered.startswith("location:") or lowered.startswith("nearby_npcs"):
        return 1
    if lowered.startswith("event:"):
        return 1
    if lowered.startswith("session"):
        return 0
    if lowered.startswith("rag:"):
        return max_proximity_hops + 1
    return max_proximity_hops


def _normalize_ratio(value: float) -> float:
    return max(0.0, min(1.0, value))
