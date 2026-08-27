"""
Module: embedding_index
Layer: retrieval
Purpose: Indexes text snippets and retrieves semantically similar entries.
Does NOT: persist vectors outside selected vector store backend.
Dependencies injected: VectorStoreProtocol.
Used by: retrieval.context_builder, engines.gossip.gossip_handler, engines.events.event_handler.
"""

from __future__ import annotations

from typing import Any
import asyncio

from .vector_store_protocol import VectorSearchResult, VectorStoreProtocol

EMBED_DIMENSION = 384  # all-MiniLM-L6-v2 output dimension


def _embed_text(text: str, model_name: str) -> list[float]:
    if text == "":
        return [0.0] * EMBED_DIMENSION
    from .sentence_encoder import embed
    return embed(text, model_name=model_name)


def _embed_texts_batch(texts: list[str], model_name: str) -> list[list[float]]:
    if not texts:
        return []
    return [_embed_text(t, model_name) for t in texts]


class EmbeddingIndex:
    """Thin embedding layer over a vector store backend."""

    def __init__(self, vector_store: VectorStoreProtocol, model_name: str) -> None:
        """Initialise the index backed by the given vector store.

        Args:
            vector_store: Backend store implementing VectorStoreProtocol.
            model_name: HuggingFace model identifier for embedding (e.g. "all-MiniLM-L6-v2").
        """

        self._vector_store = vector_store
        self._model_name = model_name

    async def upsert(self, item_id: str, text: str, payload: dict[str, Any]) -> None:
        """Embed text and upsert into the vector store.

        Args:
            item_id: Unique identifier for the indexed item.
            text: Raw text to embed; empty string produces a zero vector.
            payload: Arbitrary metadata stored alongside the embedding.
        """

        # Offload the CPU-bound sentence-transformers encode to a worker thread so
        # it never blocks the asyncio event loop (ISSUE-063).
        vector = await asyncio.to_thread(_embed_text, text, self._model_name)
        await self._vector_store.upsert(item_id=item_id, vector=vector, payload=payload)

    @property
    def model_name(self) -> str:
        """Return the embedding model identifier this index encodes with.

        Exposed because the corpus fingerprint records which model produced the stored
        vectors: changing EMBEDDING_MODEL invalidates every vector and every prior
        measurement, and nothing could previously say so (DEC-211).
        """

        return self._model_name

    async def upsert_vector(
        self, item_id: str, vector: list[float], payload: dict[str, Any]
    ) -> None:
        """Store an ALREADY-COMPUTED vector, without encoding anything.

        The insert path for corpus population (DEC-208). `upsert` above encodes its text;
        this one deliberately cannot, because the embeddings persisted on the node were
        produced by the reconciler's embedding TEXT and re-deriving that text here would
        be a second implementation of it, free to disagree. sentence_encoder.embed
        normalises, so the store's dot product over these vectors is already cosine.

        Args:
            item_id: Unique identifier for the indexed item.
            vector: Precomputed embedding vector.
            payload: Arbitrary metadata stored alongside the embedding.
        """

        await self._vector_store.upsert(item_id=item_id, vector=vector, payload=payload)

    async def count(self) -> int:
        """Return how many entries the backing vector store holds.

        Returns:
            Number of stored entries.
        """

        return await self._vector_store.count()

    async def search(
        self,
        query: str,
        top_k: int,
        filter_ids: set[str] | None = None,
    ) -> list[VectorSearchResult]:
        """Return up to top_k results nearest to the embedded query.

        Args:
            query: Text to embed and use as the search query.
            top_k: Maximum number of results; must be greater than 0.
            filter_ids: When provided, only these ids are candidates. The filter is
                pushed DOWN into the store so it restricts the candidate set before
                ranking (DEC-209); this used to filter the ranked output here, which made
                a filtered search over a mixed store return 0-1 rows. An empty set is a
                real empty scope and yields no results.

        Returns:
            List of VectorSearchResult dicts sorted by descending similarity score.

        Raises:
            ValueError: If top_k is not greater than 0.
        """

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        query_vector = await asyncio.to_thread(_embed_text, query, self._model_name)
        return await self._vector_store.search(
            query_vector=query_vector, top_k=top_k, filter_ids=filter_ids
        )

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode a list of texts and return their embedding vectors.

        Used by the embedding reconciler to batch-encode all stale nodes in one
        call instead of N individual encodes inside upsert.

        Args:
            texts: Raw text strings to encode; empty list returns empty list.

        Returns:
            List of float vectors, one per input text, in the same order.
            Empty texts produce a zero vector of length EMBED_DIMENSION.
        """

        return await asyncio.to_thread(_embed_texts_batch, texts, self._model_name)

    async def invalidate(self, item_id: str) -> None:
        """Remove one indexed entry from the vector store.

        Args:
            item_id: Identifier of the entry to invalidate; no-op if not found.
        """

        await self._vector_store.delete(item_id=item_id)
