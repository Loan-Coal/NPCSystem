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

from typing import TYPE_CHECKING

from npc_engine.config import Settings
from npc_engine.graph.db import GraphDB
from npc_engine.retrieval.context_builder import build_serialized_context
from npc_engine.retrieval.context_protocols import EmbeddingIndexProtocol
from npc_engine.schema.context_config_models import LLMConfig

if TYPE_CHECKING:
    from npc_engine.retrieval.dialogue_context_cache import (
        DialogueContextCache,
        PartialDialogueContextCache,
    )


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
        emotion_state: dict | None,
        context_cache: PartialDialogueContextCache | DialogueContextCache | None,
        session_id: str | None,
        skip_rag: bool,
        player_id: str | None,
        explicit_node_ids: frozenset[str],
    ) -> str:
        """Build the serialized prompt context, opening a session internally.

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
        Returns:
            Serialized context string.
        Raises:
            ValueError: If RAG_TOP_K <= 0.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await build_serialized_context(
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
            )
