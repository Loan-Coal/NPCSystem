"""
context_builder.py - Orchestrates context merge, budget enforcement, and serialization.

Does NOT: call LLM adapters.

Dependencies injected: EmbeddingIndex.
"""

from neo4j import AsyncSession
import json
from datetime import datetime
from typing import Any
from typing import Protocol

from config import Settings
from graph.graph_reader import get_character_with_relations
from retrieval.context_merger import ContextItem, merge_context
from retrieval.context_merger import MergedContext
from retrieval.context_serializer import serialize_context
from retrieval.vector_store_protocol import VectorSearchResult
from retrieval.subgraph_retriever import retrieve_tier_a_context
from retrieval.token_budget_enforcer import TokenBudgetExceededError, enforce_budget
from world.world_reader import get_world_state


class EmbeddingIndexProtocol(Protocol):
    """Minimal protocol required by context builder."""

    async def search(self, query: str, top_k: int) -> list[VectorSearchResult]:
        """Return top-k semantic retrieval rows."""


async def build_serialized_context(
    session: AsyncSession,
    settings: Settings,
    embedding_index: EmbeddingIndexProtocol,
    npc_id: str,
    player_message: str,
    session_turns: list[str],
    emotion_state: dict | None = None,
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
    tier0 = [
        ContextItem(key="world", text=world_state.model_dump_json(), tier="tier0", priority=100),
        ContextItem(
            key="emotion",
            text=json.dumps(emotion_snapshot, ensure_ascii=True, sort_keys=True),
            tier="tier0",
            priority=95,
        ),
        ContextItem(
            key="session",
            text=json.dumps(session_turns, ensure_ascii=True),
            tier="tier0",
            priority=90,
        ),
    ]
    tier_a = await retrieve_tier_a_context(
        session=session,
        npc_id=npc_id,
        event_limit=settings.RAG_TOP_K,
    )
    tier_b_results = await embedding_index.search(query=player_message, top_k=settings.RAG_TOP_K)
    tier_b = [
        ContextItem(
            key=f"rag:{row['id']}",
            text=json.dumps(_to_json_safe(row["payload"]), ensure_ascii=True, sort_keys=True),
            tier="tierB",
            priority=60,
        )
        for row in tier_b_results
    ]

    merged = merge_context(tier0=tier0, tier_a=tier_a, tier_b=tier_b)
    trimmed = enforce_budget(context=merged, budget=settings.PROMPT_TOKEN_BUDGET)
    return _enforce_final_serialized_budget(
        context=trimmed,
        budget=settings.PROMPT_TOKEN_BUDGET,
    )


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


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
    """Ensure final serialized prompt stays within token budget by trimming low-priority tiers."""

    current = context
    while True:
        serialized = serialize_context(context=current)
        if _estimate_tokens(serialized) <= budget:
            return serialized

        removable_candidates = [
            item
            for item in current.items
            if item.tier in {"tierB", "tierA"}
        ]
        if len(removable_candidates) == 0:
            raise TokenBudgetExceededError("Serialized context exceeds budget after mandatory tiers")

        to_drop = sorted(
            removable_candidates,
            key=lambda item: (item.tier != "tierB", item.priority),
        )[0]
        current = current.model_copy(
            update={
                "items": [item for item in current.items if item.key != to_drop.key],
            }
        )
