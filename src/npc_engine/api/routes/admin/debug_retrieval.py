"""
Module: debug_retrieval
Layer: api
Purpose: Admin GET endpoint that runs the retrieval pipeline for (npc_id, query)
         and returns ranked context items for inspection and eval tooling.
Does NOT: call LLM adapters, mutate graph state, or perform auth itself.
Dependencies injected: AsyncSession, EmbeddingIndex, Settings, LLMConfig (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from neo4j import AsyncSession
from pydantic import BaseModel, ConfigDict

from npc_engine.api.dependencies import get_db_session, get_embedding_index
from npc_engine.api.dependency_singletons import get_llm_config
from npc_engine.retrieval.embedding import EmbeddingIndex
from npc_engine.config import Settings, get_settings
from npc_engine.retrieval.context import build_serialized_context
from npc_engine.retrieval.context import estimate_tokens
from npc_engine.schema.context_config_models import LLMConfig

router = APIRouter(prefix="/debug")

_UNKNOWN_TIER = "unknown"
_DEFAULT_PRIORITY = 0


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ContextItemView(BaseModel):
    """One parsed context item from the retrieval pipeline output.

    Tier and priority default to sentinel values when not recoverable from
    the serialized prompt blob (build_serialized_context flattens metadata).
    """

    key: str
    tier: str
    priority: int
    text: str

    model_config = ConfigDict(frozen=True)


class DebugRetrievalResponse(BaseModel):
    """Response body for GET /debug/retrieval.

    Attributes:
        npc_id: The NPC whose retrieval context was built.
        query: The player query used as the retrieval signal.
        context_items: Parsed top-level entries from the serialized context.
        total_tokens: Estimated token count of the serialized context blob.
    """

    npc_id: str
    query: str
    context_items: list[ContextItemView]
    total_tokens: int

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_context_items(serialized: str) -> list[ContextItemView]:
    """Parse the serialized context blob into a flat list of ContextItemView entries.

    build_serialized_context returns a compact JSON object whose top-level keys
    represent context sections. Tier and priority metadata are not preserved in
    the serialized form, so they are set to sentinel defaults.

    Args:
        serialized: JSON string returned by build_serialized_context.

    Returns:
        List of ContextItemView, one per top-level key in the JSON object.
        Returns an empty list when the JSON object is empty or the string is blank.
    """
    if not serialized:
        return []
    try:
        parsed = json.loads(serialized)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, dict):
        return []
    items: list[ContextItemView] = []
    for key, value in parsed.items():
        text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        items.append(
            ContextItemView(
                key=key,
                tier=_UNKNOWN_TIER,
                priority=_DEFAULT_PRIORITY,
                text=text,
            )
        )
    return items


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get("/retrieval", response_model=DebugRetrievalResponse)
async def get_debug_retrieval(
    npc_id: str = Query(..., description="NPC identifier to retrieve context for"),
    query: str = Query(..., description="Player query used as retrieval signal"),
    session: AsyncSession = Depends(get_db_session),
    embedding_index: EmbeddingIndex = Depends(get_embedding_index),
    settings: Settings = Depends(get_settings),
    llm_config: LLMConfig = Depends(get_llm_config),
) -> DebugRetrievalResponse:
    """Return the ranked retrieval context for a given NPC and query.

    Runs the full retrieval pipeline (graph + vector RAG) and exposes the
    resulting context as a structured list of items. Intended for eval
    tooling and developer inspection — not for game client use.

    Args:
        npc_id: The NPC identifier whose context is assembled.
        query: Player message used as the retrieval signal.
        session: Scoped Neo4j session.
        embedding_index: Singleton vector store index.
        settings: Application settings.
        llm_config: Context-pipeline config (tier budgets, weights).

    Returns:
        DebugRetrievalResponse with parsed context items and token estimate.
    """
    serialized = await build_serialized_context(
        session=session,
        settings=settings,
        llm_config=llm_config,
        embedding_index=embedding_index,
        npc_id=npc_id,
        player_message=query,
        session_turns=[],
    )
    items = _parse_context_items(serialized)
    total_tokens = estimate_tokens(serialized) if serialized else 0
    return DebugRetrievalResponse(
        npc_id=npc_id,
        query=query,
        context_items=items,
        total_tokens=total_tokens,
    )
