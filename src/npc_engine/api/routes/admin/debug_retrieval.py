"""
Module: debug_retrieval
Layer: api
Purpose: Admin GET endpoint that runs the retrieval pipeline for one (npc_id, query)
         under a NAMED ARM and returns both the serialized slots and the context
         receipt, for inspection and for the P9 arm probe.
Does NOT: call LLM adapters, mutate graph state, or perform auth itself.
Dependencies injected: AsyncSession, EmbeddingIndex, Settings, LLMConfig,
         PartialDialogueContextCache (via FastAPI Depends).
Used by: api.router_registry (registered at admin_prefix); evals/arm_probe.py;
         scripts/probe_inner_life.py.

WHY THIS ROUTE TAKES A player_id AND A PROFILE (P9)
Every inner-life number from P0 to P8 was measured here, and this route passed neither.
`get_reputation_context_for_npc` and CYPHER_PROPAGATED_REPUTATION_FOR_NPC both match
against "" when player_id is absent, so `player_reputation`, `propagated_reputation` and
`player_relation` were structurally invisible to the instrument that was being used to
declare them present or absent. With no profile the route always assembled the default
arm, so it could not observe an arm difference at all — which is exactly what P9's gate 4
needs it to do. Both are correctness dependencies of the 8/8 headline, not conveniences.

Measured on the eval baseline before this change, captain_sorn / "what news": this route
reported 11 slot names and 978 tokens where the dialogue turn's receipt reported 16 item
keys and 1013 tokens, and the route could name no arm.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from neo4j import AsyncSession

from npc_engine.api.dependencies import get_db_session, get_embedding_index
from npc_engine.api.dependency_singletons import get_context_cache, get_llm_config
from npc_engine.api.routes.admin.debug_retrieval_models import (
    DebugRetrievalResponse,
    parse_context_items,
)
from npc_engine.config import Settings, get_settings
from npc_engine.retrieval.context import build_serialized_context_with_receipt, estimate_tokens
from npc_engine.retrieval.dialogue_context.dialogue_context_cache import (
    PartialDialogueContextCache,
)
from npc_engine.retrieval.embedding import EmbeddingIndex
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.schema.retrieval_profile_models import DEFAULT_RETRIEVAL_PROFILE_NAME

router = APIRouter(prefix="/debug")

# Annotated rather than `x: T = Query(...)` so the PYTHON default is a real value. The
# handler is called directly by unit tests and by nothing else in src/; with a bare Query
# default those calls receive the Query object itself, which fails deep inside assembly
# ("'Query' object is not iterable") rather than at the boundary.
_NpcId = Annotated[str, Query(description="NPC identifier to retrieve context for")]
_QueryText = Annotated[str, Query(description="Player query used as retrieval signal")]
_PlayerId = Annotated[
    str | None,
    Query(
        description=(
            "Player the context is assembled FOR. Omitting it leaves the three "
            "reputation slots structurally empty — that is not evidence of absence."
        )
    ),
]
_ProfileName = Annotated[
    str | None,
    Query(
        description=(
            "Named A/B arm. Resolved STRICTLY (DEC-194): an undeclared name is a 400, "
            "never a silent fallback to default."
        )
    ),
]
_SessionTurns = Annotated[
    list[str],
    Query(
        description=(
            "Conversation history, one turn per repeat of this parameter. expand_query "
            "folds it into the RAG query, so an empty history retrieves on a different "
            "signal than a real turn does."
        )
    ),
]
_SessionId = Annotated[
    str | None, Query(description="Session key for the legacy whole-context cache.")
]
_UseContextCache = Annotated[
    bool,
    Query(
        description=(
            "Share the process-wide dialogue context cache. Default OFF: the arm probe "
            "sweeps arms back to back, and a cache HIT publishes no receipt at all."
        )
    ),
]


@router.get("/retrieval", response_model=DebugRetrievalResponse)
async def get_debug_retrieval(
    npc_id: _NpcId,
    query: _QueryText,
    player_id: _PlayerId = None,
    retrieval_profile: _ProfileName = None,
    session_turn: _SessionTurns | None = None,
    session_id: _SessionId = None,
    use_context_cache: _UseContextCache = False,
    session: AsyncSession = Depends(get_db_session),
    embedding_index: EmbeddingIndex = Depends(get_embedding_index),
    settings: Settings = Depends(get_settings),
    llm_config: LLMConfig = Depends(get_llm_config),
    context_cache: PartialDialogueContextCache = Depends(get_context_cache),
) -> DebugRetrievalResponse:
    """Assemble one turn's retrieval context the way a dialogue turn does, and report it.

    Runs the full pipeline (graph + vector RAG) under the requested arm and returns both
    the serialized slots and the receipt of what reached the model. Intended for eval
    tooling and developer inspection — not for game client use.

    Args:
        npc_id: The NPC whose context is assembled.
        query: Player message used as the retrieval signal.
        player_id: Player the context is assembled for; None leaves reputation empty.
        retrieval_profile: Named arm; None means the deployment default.
        session_turn: Conversation history turns, in order.
        session_id: Legacy whole-context cache key.
        use_context_cache: Whether to share the process-wide context cache.
        session: Scoped Neo4j session.
        embedding_index: Singleton vector store index.
        settings: Application settings.
        llm_config: Context-pipeline config (tier budgets, weights).
        context_cache: Process-wide partial context cache.

    Returns:
        DebugRetrievalResponse with the slots, the receipt and a token estimate.

    Raises:
        RetrievalProfileNotFoundError: When retrieval_profile names an undeclared arm.
            Surfaced as HTTP 400 by the app's exception handlers (DEC-194 decision 2).
    """
    serialized, receipt = await build_serialized_context_with_receipt(
        session=session,
        settings=settings,
        llm_config=llm_config,
        embedding_index=embedding_index,
        npc_id=npc_id,
        player_message=query,
        session_turns=list(session_turn or []),
        context_cache=context_cache if use_context_cache else None,
        session_id=session_id,
        player_id=player_id,
        retrieval_profile=retrieval_profile,
    )
    return DebugRetrievalResponse(
        npc_id=npc_id,
        query=query,
        player_id=player_id,
        retrieval_profile=receipt.retrieval_profile
        if receipt is not None
        else (retrieval_profile or DEFAULT_RETRIEVAL_PROFILE_NAME),
        context_items=parse_context_items(serialized),
        context_receipt=receipt,
        total_tokens=estimate_tokens(serialized) if serialized else 0,
    )
