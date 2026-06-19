"""
Module: dialogue_context_port
Layer: engines
Purpose: Port Protocol for the serialized context pipeline used by DialogueHandler.
Does NOT: import neo4j types; hold sessions; implement retrieval logic.
Dependencies: retrieval.context_protocols (TYPE_CHECKING only), cache types
Used by: engines.dialogue.dialogue_handler, retrieval.dialogue_context_adapter
Dependencies injected: None (Protocol only — concrete adapters are injected by the composition root)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Any

if TYPE_CHECKING:
    from npc_engine.retrieval.dialogue_context_cache import (
        DialogueContextCache,
        PartialDialogueContextCache,
    )
    from npc_engine.engines.dialogue.system_state_context import SystemStateContext


class DialogueContextPort(Protocol):
    """Abstraction over the serialized-context retrieval pipeline.

    Implementations open their own Neo4j sessions and are responsible for all
    graph reads, RAG retrieval, and tier-budget assembly.  The engine passes
    only request-scoped data (no session, no settings, no embedding_index).
    """

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
        system_state_context: SystemStateContext | None = None,
    ) -> tuple[str, list[str]]:
        """Build and return the serialized prompt context and used memory IDs.

        Args:
            npc_id: NPC identifier for context assembly.
            player_message: Raw player utterance for RAG query and tier-B retrieval.
            session_turns: Prior turns in this session for injection into context.
            emotion_state: Current emotion snapshot (e.g. {"current_mood": "neutral"}).
            context_cache: Optional partial or full dialogue context cache.
            session_id: Session identifier used for legacy cache keying.
            skip_rag: When True, skip the RAG tier-B fetch (graph-only fallback tier).
            player_id: Player identifier for player-relation context.
            explicit_node_ids: Additional node IDs to force-include in context.
            system_state_context: Optional engine-resolved live state (ISSUE-071).
        Returns:
            Tuple of (serialized_context_str, used_memory_ids) where
            used_memory_ids is the list of Memory node IDs that made it into
            the final context (ISSUE-107).
        Raises:
            ValueError: If RAG_TOP_K <= 0.
        """
        ...
