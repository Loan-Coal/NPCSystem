"""
Module: dialogue_context_port
Layer: engines
Purpose: Port Protocol for the serialized context pipeline used by DialogueHandler.
Does NOT: import neo4j types; hold sessions; implement retrieval logic.
Dependencies: retrieval.context_protocols, retrieval.context_receipt (TYPE_CHECKING only), cache types
Used by: engines.dialogue.dialogue_handler, retrieval.dialogue_context_adapter
Dependencies injected: None (Protocol only — concrete adapters are injected by the composition root)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Any

if TYPE_CHECKING:
    from npc_engine.retrieval.dialogue_context import (
        DialogueContextCache,
        PartialDialogueContextCache,
    )
    from npc_engine.engines.dialogue.system_state_context import SystemStateContext
    from npc_engine.retrieval.context.context_receipt import ContextReceipt


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
        retrieval_profile: str | None = None,
    ) -> tuple[str, list[str], ContextReceipt | None]:
        """Build the serialized prompt context, the used memory IDs, and the assembly receipt.

        Args:
            npc_id, player_message, session_turns: The turn's request-scoped inputs.
            emotion_state: Current emotion snapshot (e.g. {"current_mood": "neutral"}).
            context_cache, session_id: Dialogue context cache and its legacy key.
            skip_rag: When True, skip the RAG tier-B fetch (graph-only fallback tier).
            player_id: Player identifier for player-relation context.
            explicit_node_ids: Additional node IDs to force-include in context.
            system_state_context: Optional engine-resolved live state (ISSUE-071).
            retrieval_profile: Named retrieval config for this turn (the A/B switch).
        Returns:
            (serialized_context_str, used_memory_ids, receipt). used_memory_ids lists the
            Memory node IDs that reached the final context (ISSUE-107). receipt describes
            what actually reached the model; None on a cached-context turn, since an empty
            receipt would read as "nothing reached the model", which is false.
        Raises:
            ValueError: If RAG_TOP_K <= 0.
            RetrievalProfileNotFoundError: If retrieval_profile is not declared. Never a
                fallback — a run must not record a profile it did not use.
        """
        ...
