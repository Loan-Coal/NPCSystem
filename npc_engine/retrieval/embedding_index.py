"""
embedding_index.py - Indexes text snippets and retrieves semantically similar entries.

Does NOT: persist vectors outside selected vector store backend.

Dependencies injected: VectorStoreProtocol.
"""

from retrieval.vector_store_protocol import VectorSearchResult, VectorStoreProtocol


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

    def __init__(self, vector_store: VectorStoreProtocol):
        self._vector_store = vector_store

    async def upsert(self, item_id: str, text: str, payload: dict) -> None:
        """Embed text and upsert into vector store."""

        vector = _embed_text(text)
        await self._vector_store.upsert(item_id=item_id, vector=vector, payload=payload)

    async def search(self, query: str, top_k: int) -> list[VectorSearchResult]:
        """Search nearest payloads by embedded query vector."""

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        query_vector = _embed_text(query)
        return await self._vector_store.search(query_vector=query_vector, top_k=top_k)

    async def invalidate(self, item_id: str) -> None:
        """Invalidate one indexed entry."""

        await self._vector_store.delete(item_id=item_id)
