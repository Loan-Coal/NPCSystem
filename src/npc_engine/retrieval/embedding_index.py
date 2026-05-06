"""
embedding_index.py - Indexes text snippets and retrieves semantically similar entries.

Does NOT: persist vectors outside selected vector store backend.

Dependencies injected: VectorStoreProtocol.
"""

from npc_engine.retrieval.vector_store_protocol import VectorSearchResult, VectorStoreProtocol


EMBED_DIMENSION = 16


def _embed_text(text: str) -> list[float]:
    vector = [0.0] * EMBED_DIMENSION
    if text == "":
        return vector
    for index, char in enumerate(text):
        slot = index % EMBED_DIMENSION
        vector[slot] += float(ord(char) % 101)
    scale = float(max(1, len(text)))
    return [value / scale for value in vector]


class EmbeddingIndex:
    """Thin embedding layer over a vector store backend."""

    def __init__(self, vector_store: VectorStoreProtocol) -> None:
        """Initialise the index backed by the given vector store.

        Args:
            vector_store: Backend store implementing VectorStoreProtocol.
        """

        self._vector_store = vector_store

    async def upsert(self, item_id: str, text: str, payload: dict) -> None:
        """Embed text and upsert into the vector store.

        Args:
            item_id: Unique identifier for the indexed item.
            text: Raw text to embed; empty string produces a zero vector.
            payload: Arbitrary metadata stored alongside the embedding.
        """

        vector = _embed_text(text)
        await self._vector_store.upsert(item_id=item_id, vector=vector, payload=payload)

    async def search(self, query: str, top_k: int) -> list[VectorSearchResult]:
        """Return up to top_k results nearest to the embedded query.

        Args:
            query: Text to embed and use as the search query.
            top_k: Maximum number of results; must be greater than 0.

        Returns:
            List of VectorSearchResult dicts sorted by descending similarity score.

        Raises:
            ValueError: If top_k is not greater than 0.
        """

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        query_vector = _embed_text(query)
        return await self._vector_store.search(query_vector=query_vector, top_k=top_k)

    async def invalidate(self, item_id: str) -> None:
        """Remove one indexed entry from the vector store.

        Args:
            item_id: Identifier of the entry to invalidate; no-op if not found.
        """

        await self._vector_store.delete(item_id=item_id)
