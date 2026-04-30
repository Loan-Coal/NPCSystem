"""
context_builder.py - Orchestrates context merge, relevance scoring, budget enforcement, and serialization.

Does NOT: call LLM adapters.

Dependencies injected: EmbeddingIndex.
"""

from typing import Protocol
import json
from datetime import datetime, timezone
from typing import Any

from neo4j import AsyncSession

from common.json_utils import parse_json_object
from config import Settings
from engines.dialogue.context_relevance_engine import ContextRelevanceCandidate, rank_context_candidates
from graph.graph_reader import get_character_with_relations
from retrieval.context_budget_enforcer import (
    COMPRESSION_SUFFIX,
    ContextBudgetError,
    ContextCompressionCache,
    enforce_context_budget,
)
from retrieval.context_merger import ContextItem, merge_context
from retrieval.context_merger import MergedContext
from retrieval.context_serializer import serialize_context
from retrieval.context_utils import estimate_tokens, parse_node_identity, serialize_json
from retrieval.dialogue_context_cache import DialogueContextCache
from retrieval.vector_store_protocol import VectorSearchResult
from retrieval.subgraph_retriever import retrieve_tier_a_context
from schema.llm_config_models import LLMConfig
from utils.metrics import increment_metric
from world.world_reader import get_world_state


CONTEXT_ITEMS_SELECTED_METRIC = "context_items_selected_total"
CONTEXT_TIER_TOKENS_METRIC = "context_tier_tokens"
CONTEXT_BUDGET_ERRORS_METRIC = "context_budget_errors_total"
LLM_COMPRESSIONS_METRIC = "llm_compressions_total"
CONTEXT_CACHE_HITS_METRIC = "dialogue_context_cache_hits_total"
CONTEXT_CACHE_MISSES_METRIC = "dialogue_context_cache_misses_total"


class EmbeddingIndexProtocol(Protocol):
    """Minimal protocol required by context builder."""

    async def search(self, query: str, top_k: int) -> list[VectorSearchResult]:
        """Return top-k semantic retrieval rows."""


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
) -> str:
    """Build final serialized prompt context string."""

    if settings.RAG_TOP_K <= 0:
        raise ValueError("RAG_TOP_K must be greater than 0")

    world_state = await get_world_state(session=session)
    character_bundle = await get_character_with_relations(session=session, npc_id=npc_id)
    character_payload = character_bundle.get("character")
    emotion_snapshot = emotion_state or {"current_mood": "neutral"}
    if emotion_state is None and isinstance(character_payload, dict):
        emotion_snapshot = {
            "current_mood": str(character_payload.get("current_mood", "neutral")),
        }

    if context_cache is not None and session_id is not None:
        npc_ts = str(character_payload.get("last_graph_updated_at", "")) if isinstance(character_payload, dict) else ""
        world_ts = world_state.last_updated_at.isoformat() if world_state.last_updated_at else ""
        current_mood = str(emotion_snapshot.get("current_mood", "neutral"))
        cache_key = context_cache.build_key(
            npc_id=npc_id,
            session_id=session_id,
            npc_last_graph_updated_at=npc_ts,
            world_last_updated_at=world_ts,
            current_mood=current_mood,
        )
        cached = context_cache.get(cache_key)
        if cached is not None:
            increment_metric(metric=CONTEXT_CACHE_HITS_METRIC, labels={"npc_id": npc_id})
            return cached
        increment_metric(metric=CONTEXT_CACHE_MISSES_METRIC, labels={"npc_id": npc_id})
    else:
        cache_key = None
    tier0 = [
        ContextItem(key="world", text=world_state.model_dump_json(), tier="tier0", priority=100),
        ContextItem(
            key="emotion",
            text=serialize_json(emotion_snapshot),
            tier="tier0",
            priority=95,
        ),
    ]
    tier_a_raw = [
        ContextItem(
            key="session",
            text=serialize_json(session_turns),
            tier="tierA",
            priority=99,
        ),
    ]

    tier_a_raw.extend(
        await retrieve_tier_a_context(
            session=session,
            npc_id=npc_id,
            event_limit=settings.RAG_TOP_K,
        )
    )

    tier_b_raw: list[ContextItem] = []
    tier_c_raw: list[ContextItem] = []
    vector_scores: dict[str, float] = {}
    if not skip_rag:
        tier_b_results = await embedding_index.search(query=player_message, top_k=settings.RAG_TOP_K)
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
        vector_scores = {f"rag:{row['id']}": _normalize_ratio(float(row.get("score", 0.0))) for row in tier_b_results}
    tier_a = _rank_tier_items(items=tier_a_raw, llm_config=llm_config, vector_scores=vector_scores)
    tier_b = _rank_tier_items(items=tier_b_raw, llm_config=llm_config, vector_scores=vector_scores)
    tier_c = _rank_tier_items(items=tier_c_raw, llm_config=llm_config, vector_scores=vector_scores)

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

    final_context, serialized = _enforce_final_serialized_budget_with_context(
        context=trimmed,
        budget=settings.PROMPT_TOKEN_BUDGET,
    )
    _record_context_metrics(context=final_context)
    _record_compression_metrics(pre_budget_context=merged, post_budget_context=final_context)

    if context_cache is not None and cache_key is not None:
        context_cache.set(cache_key, serialized)

    return serialized


def _estimate_tokens(text: str) -> int:
    return estimate_tokens(text)


def _to_json_safe(value: Any) -> Any:
    """Recursively normalize runtime values to JSON-serializable primitives."""

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _to_json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_to_json_safe(item) for item in value]

    to_native = getattr(value, "to_native", None)
    if callable(to_native):
        try:
            return _to_json_safe(to_native())
        except Exception:
            return str(value)

    return value


def _enforce_final_serialized_budget(context: MergedContext, budget: int) -> str:
    """Ensure final serialized prompt stays within token budget by trimming compressible tiers only."""

    _, serialized = _enforce_final_serialized_budget_with_context(context=context, budget=budget)
    return serialized


def _enforce_final_serialized_budget_with_context(context: MergedContext, budget: int) -> tuple[MergedContext, str]:
    """Return final merged context and serialized payload after total prompt budget trimming."""

    current = context
    while True:
        serialized = serialize_context(context=current)
        if _estimate_tokens(serialized) <= budget:
            return current, serialized

        removable_candidates = [
            item
            for item in current.items
            if item.tier in {"tierC", "tierB"}
        ]
        if len(removable_candidates) == 0:
            used_tokens = _estimate_tokens(serialized)
            raise ContextBudgetError(
                tier="total_prompt",
                used_tokens=used_tokens,
                budget_tokens=budget,
                detail="Serialized context exceeds total prompt budget after compressible tier trimming.",
            )

        to_drop = sorted(
            removable_candidates,
            key=lambda item: (item.tier != "tierC", item.priority),
        )[0]
        current = current.model_copy(
            update={
                "items": [item for item in current.items if item.key != to_drop.key],
            }
        )


def _rank_tier_items(
    *,
    items: list[ContextItem],
    llm_config: LLMConfig,
    vector_scores: dict[str, float],
) -> list[ContextItem]:
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
        explicit=1.0 if item.tier == "tierA" else 0.0,
    )

def _extract_recency_score(payload: dict[str, Any]) -> float:
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
    raw_severity = payload.get("severity")
    if isinstance(raw_severity, (int, float)):
        return _normalize_ratio(float(raw_severity) / 100.0)
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


def _record_context_metrics(context: MergedContext) -> None:
    """Emit item-count and token-count metrics for each context tier."""

    for tier in ("tier0", "tierA", "tierB", "tierC"):
        tier_items = [item for item in context.items if item.tier == tier]
        tier_count = len(tier_items)
        tier_tokens = sum(_estimate_tokens(item.text) for item in tier_items)
        if tier_count > 0:
            increment_metric(
                metric=CONTEXT_ITEMS_SELECTED_METRIC,
                amount=float(tier_count),
                labels={"tier": tier.lower()},
            )
        increment_metric(
            metric=CONTEXT_TIER_TOKENS_METRIC,
            amount=float(tier_tokens),
            labels={"tier": tier.lower()},
        )


def _record_compression_metrics(pre_budget_context: MergedContext, post_budget_context: MergedContext) -> None:
    """Emit compression count metric when budget enforcement compresses any items."""

    pre_budget_map = {item.key: item.text for item in pre_budget_context.items}
    compressed_count = sum(
        1
        for item in post_budget_context.items
        if item.key in pre_budget_map
        and item.text != pre_budget_map[item.key]
        and COMPRESSION_SUFFIX in item.text
    )
    if compressed_count > 0:
        increment_metric(metric=LLM_COMPRESSIONS_METRIC, amount=float(compressed_count), labels={"engine": "dialogue"})
