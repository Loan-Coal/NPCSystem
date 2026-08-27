"""
Module: corpus_refresher
Layer: retrieval
Purpose: The session-owning adapter that lets an engine handler refresh ONE node's
         vector-store entry without knowing anything about Neo4j or embeddings.
Does NOT: decide whether a refresh should happen (the flag lives in the handler), encode
          text, or write the graph.
Dependencies injected: graph_db, embedding index, reconciler — all via __init__.
Used by: api.dependencies_engines.core (composition root), which hands it to
         EventHandler and GossipHandler as a CorpusRefresherProtocol.
"""

from __future__ import annotations

from typing import Any

from npc_engine.retrieval.embedding.corpus import (
    CorpusReconcilerProtocol,
    CorpusStoreProtocol,
    refresh_corpus_node,
)

__all__ = ["EmbeddingCorpusRefresher"]


class EmbeddingCorpusRefresher:
    """Refreshes one node's vector-store entry, opening its own short-lived session.

    The handlers hold repository PORTS, not sessions, and giving them a session to carry
    would push graph lifetime management into the engines layer. This adapter owns that
    lifetime instead, so the handler's dependency stays `refresh(node_id) -> bool`.
    """

    def __init__(
        self,
        graph_db: Any,
        embedding_index: CorpusStoreProtocol,
        reconciler: CorpusReconcilerProtocol,
    ) -> None:
        """Initialise the refresher.

        Args:
            graph_db: Graph database handle providing get_session().
            embedding_index: Vector store to write the refreshed entry into.
            reconciler: Reconciler run for one pass so the node gets an embedding.
        """
        self._graph_db = graph_db
        self._embedding_index = embedding_index
        self._reconciler = reconciler

    async def refresh(self, node_id: str) -> bool:
        """Re-embed pending nodes and write this node's entry into the store.

        Args:
            node_id: Identifier of the node to refresh.

        Returns:
            True when an entry was written; False when the node carries no embedding.
        """
        async with self._graph_db.get_session() as session:
            return await refresh_corpus_node(
                session, self._embedding_index, self._reconciler, node_id=node_id,
            )
