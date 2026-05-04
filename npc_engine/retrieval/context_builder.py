"""
context_builder.py - Orchestrates context merge, relevance scoring, budget enforcement, and serialization.

Does NOT: call LLM adapters.

Dependencies injected: EmbeddingIndex.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Protocol

from neo4j import AsyncSession

from config import Settings
from graph.graph_reader import get_character_with_relations
from retrieval.context_budget_enforcer import ContextCompressionCache, enforce_context_budget
from retrieval.context_merger import ContextItem, MergedContext, merge_context
from retrieval.context_metrics import (
    CONTEXT_BUDGET_ERRORS_METRIC,
    CONTEXT_CACHE_HITS_METRIC,
    CONTEXT_CACHE_MISSES_METRIC,
    record_compression_metrics,
    record_context_metrics,
)
from retrieval.context_scoring import rank_tier_items
from retrieval.context_serializer import serialize_context
from retrieval.context_utils import serialize_json
from retrieval.dialogue_context_cache import DialogueContextCache
from retrieval.subgraph_retriever import retrieve_tier_a_context
from retrieval.vector_store_protocol import VectorSearchResult
from schema.llm_config_models import LLMConfig
from utils.errors import ContextBudgetError
from utils.metrics import increment_metric
from world.world_reader import get_world_state


class EmbeddingIndexProtocol(Protocol):
    """Minimal protocol required by context builder."""

    async def search(self, query: str, top_k: int) -> list[VectorSearchResult]:
        """Return top-k semantic retrieval rows.

        Args:
            query: Text query to embed and search.
            top_k: Maximum number of results to return.

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
) -> str:
    """Build the final serialized prompt context string for one dialogue turn.

    Assembles tier0 (world, emotion), tierA (graph facts, session history),
    tierB/C (RAG results), applies relevance scoring, budget enforcement,
    and serializes to JSON.

    Args:
        session: Active Neo4j async session.
        settings: Application settings (RAG_TOP_K, PROMPT_TOKEN_BUDGET).
        llm_config: LLM configuration with tier budgets and relevance weights.
        embedding_index: Vector index used for RAG retrieval.
        npc_id: ID of the NPC whose context is being built.
        player_message: Current player message used as the RAG query.
        session_turns: Recent dialogue history as serialized strings.
        emotion_state: Optional emotion snapshot; derived from character payload if omitted.
        compression_cache: Optional pre-warmed compression cache.
        context_cache: Optional in-memory dialogue context cache.
        session_id: Session identifier used as part of the context cache key.
        skip_rag: When True, skips vector store retrieval entirely.

    Returns:
        Compact JSON string ready for prompt injection.

    Raises:
        ValueError: If RAG_TOP_K is not greater than 0.
        ContextBudgetError: If tier A or total prompt budget cannot be satisfied.
    """

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

    cache_key = None
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

    tier0 = [
        ContextItem(key="world", text=world_state.model_dump_json(), tier="tier0", priority=100),
        ContextItem(key="emotion", text=serialize_json(emotion_snapshot), tier="tier0", priority=95),
    ]
    tier_a_raw = [
        ContextItem(key="session", text=serialize_json(session_turns), tier="tierA", priority=99),
    ]
    tier_a_raw.extend(
        await retrieve_tier_a_context(session=session, npc_id=npc_id, event_limit=settings.RAG_TOP_K)
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
        vector_scores = {
            f"rag:{row['id']}": _normalize_ratio(float(row.get("score", 0.0)))
            for row in tier_b_results
        }

    tier_a = rank_tier_items(items=tier_a_raw, llm_config=llm_config, vector_scores=vector_scores)
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

    final_context, serialized = _enforce_final_serialized_budget_with_context(
        context=trimmed,
        budget=settings.PROMPT_TOKEN_BUDGET,
    )
    record_context_metrics(context=final_context)
    record_compression_metrics(pre_budget_context=merged, post_budget_context=final_context)

    if context_cache is not None and cache_key is not None:
        context_cache.set(cache_key, serialized)

    return serialized


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


def _enforce_final_serialized_budget_with_context(context: MergedContext, budget: int) -> tuple[MergedContext, str]:
    """Trim compressible tiers until the serialized prompt fits within the token budget.

    Args:
        context: Merged context to trim.
        budget: Maximum token count for the serialized prompt.

    Returns:
        Tuple of (final MergedContext, serialized JSON string).

    Raises:
        ContextBudgetError: If the prompt cannot fit within budget after all compressible items are dropped.
    """

    from retrieval.context_utils import estimate_tokens

    current = context
    while True:
        serialized = serialize_context(context=current)
        if estimate_tokens(serialized) <= budget:
            return current, serialized

        removable_candidates = [item for item in current.items if item.tier in {"tierC", "tierB"}]
        if len(removable_candidates) == 0:
            used_tokens = estimate_tokens(serialized)
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


def _normalize_ratio(value: float) -> float:
    return max(0.0, min(1.0, value))


def _enforce_final_serialized_budget(context: MergedContext, budget: int) -> str:
    _, serialized = _enforce_final_serialized_budget_with_context(context=context, budget=budget)
    return serialized


def _estimate_tokens(text: str) -> int:
    from retrieval.context_utils import estimate_tokens
    return estimate_tokens(text)
