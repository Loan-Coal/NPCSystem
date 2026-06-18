"""
Unit tests: EmbeddingIndex offloads the synchronous sentence-transformers encode
to a worker thread (ISSUE-063), so CPU-bound encoding never blocks the asyncio
event loop. Before the fix, the embedding reconciler's startup batch encode ran on
the event loop and froze the single uvicorn worker, timing out the demo's pollers.
"""

from __future__ import annotations

import threading
from unittest.mock import AsyncMock

import pytest

from npc_engine.retrieval import embedding_index
from npc_engine.retrieval.embedding_index import EMBED_DIMENSION, EmbeddingIndex


@pytest.mark.asyncio
async def test_search_offloads_encode_off_event_loop_thread(monkeypatch) -> None:
    """search() encodes the query on a worker thread, not the event-loop thread."""
    captured: dict[str, str] = {}

    def _spy_embed(text: str, model_name: str) -> list[float]:
        captured["thread"] = threading.current_thread().name
        return [0.0] * EMBED_DIMENSION

    monkeypatch.setattr(embedding_index, "_embed_text", _spy_embed)
    store = AsyncMock()
    store.search.return_value = []
    index = EmbeddingIndex(vector_store=store, model_name="m")

    await index.search("q", top_k=1)

    assert captured["thread"] != threading.main_thread().name


@pytest.mark.asyncio
async def test_upsert_offloads_encode_off_event_loop_thread(monkeypatch) -> None:
    """upsert() encodes on a worker thread, not the event-loop thread."""
    captured: dict[str, str] = {}

    def _spy_embed(text: str, model_name: str) -> list[float]:
        captured["thread"] = threading.current_thread().name
        return [0.0] * EMBED_DIMENSION

    monkeypatch.setattr(embedding_index, "_embed_text", _spy_embed)
    index = EmbeddingIndex(vector_store=AsyncMock(), model_name="m")

    await index.upsert("id_1", "text", {})

    assert captured["thread"] != threading.main_thread().name


@pytest.mark.asyncio
async def test_embed_batch_offloads_encode_off_event_loop_thread(monkeypatch) -> None:
    """embed_batch() (used by the startup reconciler) encodes on a worker thread."""
    captured: dict[str, str] = {}

    def _spy_batch(texts: list[str], model_name: str) -> list[list[float]]:
        captured["thread"] = threading.current_thread().name
        return [[0.0] * EMBED_DIMENSION for _ in texts]

    monkeypatch.setattr(embedding_index, "_embed_texts_batch", _spy_batch)
    index = EmbeddingIndex(vector_store=AsyncMock(), model_name="m")

    await index.embed_batch(["a", "b"])

    assert captured["thread"] != threading.main_thread().name
