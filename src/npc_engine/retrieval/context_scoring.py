"""
context_scoring.py - Relevance scoring helpers for context tier items.

Does NOT: fetch graph/vector data or enforce token budgets.

Dependencies injected: LLMConfig.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from npc_engine.common.json_utils import parse_json_object
from npc_engine.retrieval.context_merger import ContextItem
from npc_engine.retrieval.context_relevance_engine import ContextRelevanceCandidate, rank_context_candidates
from npc_engine.retrieval.context_utils import parse_node_identity
from npc_engine.schema.context_config_models import LLMConfig


def rank_tier_items(
    *,
    items: list[ContextItem],
    llm_config: LLMConfig,
    vector_scores: dict[str, float],
) -> list[ContextItem]:
    """Score and rank context items by relevance.

    Args:
        items: Unordered context items to rank.
        llm_config: LLM configuration providing relevance weights and proximity settings.
        vector_scores: Map of item key to normalized vector similarity score.

    Returns:
        Items reordered by descending relevance score with updated priority fields.
    """

    candidates = [
        _build_candidate(item=item, llm_config=llm_config, vector_scores=vector_scores)
        for item in items
    ]
    return rank_context_candidates(
        candidates=candidates,
        weights=llm_config.relevance_weights,
        max_proximity_hops=llm_config.max_proximity_hops,
    )


def _build_candidate(
    *,
    item: ContextItem,
    llm_config: LLMConfig,
    vector_scores: dict[str, float],
) -> ContextRelevanceCandidate:
    node_type, node_id = parse_node_identity(item.key)
    payload = parse_json_object(item.text)
    return ContextRelevanceCandidate(
        node_type=node_type,
        node_id=node_id,
        item=item,
        recency=_extract_recency_score(payload),
        severity=_extract_severity_score(payload),
        proximity_hops=_infer_proximity_hops(item.key, llm_config.max_proximity_hops),
        relation=_extract_relation_score(item=item, vector_scores=vector_scores),
        quest=_quest_score(item=item),
    )


# Fields that indicate a node uses in-game time rather than wall-clock time.
# Nodes with these fields cannot be scored against datetime.now() — Phase 6 will
# add proper in-game-tick scoring once the game tick is threaded through the pipeline.
_GAME_TIME_FIELDS = frozenset({"created_at_game_time", "occurred_at_game_time"})


def _extract_recency_score(payload: dict[str, Any]) -> float:
    if any(payload.get(f) is not None for f in _GAME_TIME_FIELDS):
        return 0.0  # game-time node; can't score against wall clock
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


def _extract_relation_score(*, item: ContextItem, vector_scores: dict[str, float]) -> float:
    if item.tier == "tierB":
        return vector_scores.get(item.key, 0.0)
    return _normalize_ratio(item.priority / 100.0)


def _quest_score(*, item: ContextItem) -> float:
    lowered = item.key.lower()
    if "quest" in lowered:
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
