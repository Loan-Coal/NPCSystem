"""
test_vector_store_and_index.py - Unit tests for in-memory vector store and embedding index.

Does NOT: connect to external vector databases.

Dependencies injected: None.
"""

import pytest

from npc_engine.config import Settings
from npc_engine.retrieval.embedding_index import EmbeddingIndex
from npc_engine.retrieval.vector_store_factory import InMemoryVectorStore, create_vector_store


def _settings() -> Settings:
    return Settings(
        API_KEY_SECRET="npc_dev_secret_2026_alpha",
        NEO4J_URI="bolt://localhost:7687",
        NEO4J_USER="neo4j",
        NEO4J_PASSWORD="password",
    )


@pytest.mark.asyncio
async def test_memory_vector_store_search_sorted() -> None:
    store = InMemoryVectorStore()
    await store.upsert("a", [1.0, 0.0], {"text": "alpha"})
    await store.upsert("b", [0.0, 1.0], {"text": "beta"})
    results = await store.search(query_vector=[1.0, 0.0], top_k=2)
    assert results[0]["id"] == "a"


@pytest.mark.asyncio
async def test_embedding_index_upsert_search_invalidate() -> None:
    index = EmbeddingIndex(vector_store=InMemoryVectorStore())
    await index.upsert(item_id="npc_1", text="market fire", payload={"kind": "event"})
    results = await index.search(query="market", top_k=1)
    assert results[0]["id"] == "npc_1"
    await index.invalidate(item_id="npc_1")
    results_after_delete = await index.search(query="market", top_k=1)
    assert results_after_delete == []


@pytest.mark.asyncio
async def test_vector_store_rejects_non_positive_top_k() -> None:
    store = InMemoryVectorStore()
    await store.upsert("a", [1.0, 0.0], {"text": "alpha"})
    with pytest.raises(ValueError):
        await store.search(query_vector=[1.0, 0.0], top_k=0)


@pytest.mark.asyncio
async def test_embedding_index_rejects_non_positive_top_k() -> None:
    index = EmbeddingIndex(vector_store=InMemoryVectorStore())
    await index.upsert(item_id="npc_1", text="market fire", payload={"kind": "event"})
    with pytest.raises(ValueError):
        await index.search(query="market", top_k=-1)


def test_vector_store_factory_returns_memory_backend() -> None:
    store = create_vector_store(settings=_settings())
    assert isinstance(store, InMemoryVectorStore)
