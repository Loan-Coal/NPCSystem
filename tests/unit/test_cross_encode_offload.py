"""
test_cross_encode_offload.py - Unit tests: cross-encoder rerank runs off the event loop.

ISSUE-064 (S22.2): cross_encoder_reranker.rerank() does synchronous sentence-transformers
model inference. On the async dialogue path it must be offloaded with asyncio.to_thread so
CPU-bound reranking never blocks the single uvicorn event-loop thread (mirrors ISSUE-063).

Does NOT: load a real cross-encoder model (the rerank call is spied/patched).
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from npc_engine.retrieval import context_builder
from npc_engine.retrieval.vector_store_protocol import VectorSearchResult


def _settings(*, enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(CROSS_ENCODER_ENABLED=enabled)


@pytest.mark.asyncio
async def test_rerank_offloads_off_event_loop_thread(monkeypatch) -> None:
    """_maybe_cross_encode runs rerank on a worker thread, not the event-loop thread."""
    captured: dict[str, str] = {}

    def _spy_rerank(query: str, candidates: list[VectorSearchResult]) -> list[VectorSearchResult]:
        captured["thread"] = threading.current_thread().name
        return candidates

    monkeypatch.setattr(
        "npc_engine.retrieval.cross_encoder_reranker.rerank", _spy_rerank
    )
    results = [VectorSearchResult(id="ev_1", score=0.9, payload={})]

    out = await context_builder._maybe_cross_encode(_settings(enabled=True), "q", results)

    assert out == results
    assert captured["thread"] != threading.main_thread().name


@pytest.mark.asyncio
async def test_rerank_skipped_when_disabled(monkeypatch) -> None:
    """When CROSS_ENCODER_ENABLED is False, rerank is not called and input is returned."""
    called = {"n": 0}

    def _spy_rerank(query: str, candidates: list[VectorSearchResult]) -> list[VectorSearchResult]:
        called["n"] += 1
        return candidates

    monkeypatch.setattr(
        "npc_engine.retrieval.cross_encoder_reranker.rerank", _spy_rerank
    )
    results = [VectorSearchResult(id="ev_1", score=0.9, payload={})]

    out = await context_builder._maybe_cross_encode(_settings(enabled=False), "q", results)

    assert out == results
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_rerank_skipped_when_empty(monkeypatch) -> None:
    """Empty tier-B results short-circuit without invoking rerank."""
    called = {"n": 0}

    def _spy_rerank(query: str, candidates: list[VectorSearchResult]) -> list[VectorSearchResult]:
        called["n"] += 1
        return candidates

    monkeypatch.setattr(
        "npc_engine.retrieval.cross_encoder_reranker.rerank", _spy_rerank
    )

    out = await context_builder._maybe_cross_encode(_settings(enabled=True), "q", [])

    assert out == []
    assert called["n"] == 0
