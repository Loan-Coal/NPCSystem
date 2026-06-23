"""
Module: dialogue_context_adapter
Layer: retrieval
Purpose: Neo4j-backed adapter for DialogueContextPort — wraps build_serialized_context,
         opening a session per call so DialogueHandler holds no AsyncSession.
Does NOT: implement tier logic; import from engines layer.
Dependencies: retrieval.context_builder, retrieval.context_protocols, retrieval.dialogue_context_cache,
              graph.db, config.Settings, schema.context_config_models
Used by: api.dependencies_stores (composition root)
Dependencies injected: GraphDB, Settings, LLMConfig, EmbeddingIndexProtocol
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from npc_engine.config import Settings
from npc_engine.graph.db import GraphDB
from npc_engine.retrieval.context.context_builder import build_serialized_context
from npc_engine.retrieval.context.context_protocols import EmbeddingIndexProtocol
from npc_engine.schema.context_config_models import LLMConfig

if TYPE_CHECKING:
    from .dialogue_context_cache import (
        DialogueContextCache,
        PartialDialogueContextCache,
    )


def _extract_used_memory_ids(context_str: str) -> list[str]:
    """Parse the serialized context JSON and return memory node IDs present in it.

    Both general NPC memories and player-scoped memories are included.
    Returns an empty list when the context is missing or malformed.

    Args:
        context_str: Serialized JSON context string from build_serialized_context.

    Returns:
        List of memory node ID strings found under the "memories" and
        "player_memories" keys of the top-level context object.
    """
    try:
        ctx = json.loads(context_str)
    except (json.JSONDecodeError, ValueError):
        return []
    ids: list[str] = []
    for key in ("memories", "player_memories"):
        block = ctx.get(key)
        if not isinstance(block, list):
            continue
        for item in block:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
    return ids


class Neo4jDialogueContextAdapter:
    """Retrieval-layer adapter that satisfies DialogueContextPort.

    Holds the infrastructure deps (GraphDB, Settings, LLMConfig, embedding_index)
    so the engine no longer needs to hold or pass a session.
    Dependencies injected: graph_db, settings, llm_config, embedding_index.
    """

    def __init__(
        self,
        *,
        graph_db: GraphDB,
        settings: Settings,
        llm_config: LLMConfig,
        embedding_index: EmbeddingIndexProtocol,
    ) -> None:
        """Initialise with retrieval infrastructure.

        Args:
            graph_db: Shared database connection pool; a session is opened per call.
            settings: Application settings forwarded to the context pipeline.
            llm_config: Context tier budget and relevance weight config.
            embedding_index: Vector store for RAG retrieval.
        """
        self._graph_db = graph_db
        self._settings = settings
        self._llm_config = llm_config
        self._embedding_index = embedding_index

    async def build_context(
        self,
        *,
        npc_id: str,
        player_message: str,
        session_turns: list[str],
        emotion_state: dict[str, Any] | None,
        context_cache: PartialDialogueContextCache | DialogueContextCache | None,
        session_id: str | None,
        skip_rag: bool,
        player_id: str | None,
        explicit_node_ids: frozenset[str],
        system_state_context: Any | None = None,
    ) -> tuple[str, list[str]]:
        """Build the serialized prompt context and used memory IDs, opening a session internally.

        Args:
            npc_id: NPC identifier for context assembly.
            player_message: Raw player utterance.
            session_turns: Prior session turns.
            emotion_state: Current emotion snapshot.
            context_cache: Optional partial or full dialogue context cache.
            session_id: Session identifier for legacy cache keying.
            skip_rag: Skip RAG tier-B fetch when True.
            player_id: Player identifier.
            explicit_node_ids: Additional node IDs to force-include.
            system_state_context: Optional engine-resolved live state; typed Any to avoid
                upward layer import (SystemStateContext lives in engines layer).
        Returns:
            Tuple of (serialized_context_str, used_memory_ids).
        Raises:
            ValueError: If RAG_TOP_K <= 0.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            context_str = await build_serialized_context(
                session=session,
                settings=self._settings,
                llm_config=self._llm_config,
                embedding_index=self._embedding_index,
                npc_id=npc_id,
                player_message=player_message,
                session_turns=session_turns,
                emotion_state=emotion_state,
                context_cache=context_cache,
                session_id=session_id,
                skip_rag=skip_rag,
                player_id=player_id,
                explicit_node_ids=explicit_node_ids,
                system_state_context=system_state_context,
            )
        memory_ids = _extract_used_memory_ids(context_str)
        return context_str, memory_ids
