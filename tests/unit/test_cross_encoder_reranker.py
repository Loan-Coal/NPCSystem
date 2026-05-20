"""
test_cross_encoder_reranker.py - Unit tests for cross_encoder_reranker module.

Does NOT: download or load real ML models. Uses a monkeypatched CrossEncoder.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from npc_engine.retrieval.cross_encoder_reranker import rerank


def _result(item_id: str, content: str) -> dict:
    return {"id": item_id, "score": 0.5, "payload": {"content": content}}


def test_rerank_empty_returns_empty():
    assert rerank("query", []) == []


def test_rerank_orders_by_descending_score(monkeypatch):
    """Mock CrossEncoder.predict to return controlled scores and verify ordering."""
    mock_model = MagicMock()
    mock_model.predict.return_value = [0.1, 0.9, 0.5]

    with patch("npc_engine.retrieval.cross_encoder_reranker._get_cross_encoder", return_value=mock_model):
        candidates = [
            _result("low", "low relevance text"),
            _result("high", "very relevant text"),
            _result("mid", "somewhat relevant"),
        ]
        result = rerank("test query", candidates)

    assert result[0]["id"] == "high"
    assert result[1]["id"] == "mid"
    assert result[2]["id"] == "low"


def test_rerank_falls_back_to_content_field(monkeypatch):
    """Verify payload.content is used when summary is absent."""
    mock_model = MagicMock()
    mock_model.predict.return_value = [0.5]

    with patch("npc_engine.retrieval.cross_encoder_reranker._get_cross_encoder", return_value=mock_model):
        candidates = [{"id": "x", "score": 0.5, "payload": {"content": "some content"}}]
        result = rerank("query", candidates)

    called_pairs = mock_model.predict.call_args[0][0]
    assert called_pairs[0] == ("query", "some content")
    assert len(result) == 1


def test_rerank_prefers_summary_over_content(monkeypatch):
    """summary field takes priority over content."""
    mock_model = MagicMock()
    mock_model.predict.return_value = [0.5]

    with patch("npc_engine.retrieval.cross_encoder_reranker._get_cross_encoder", return_value=mock_model):
        candidates = [{"id": "x", "score": 0.5, "payload": {"summary": "summary text", "content": "content text"}}]
        rerank("query", candidates)

    called_pairs = mock_model.predict.call_args[0][0]
    assert called_pairs[0] == ("query", "summary text")


def test_rerank_empty_text_when_no_text_field(monkeypatch):
    """Items with no summary or content use empty string."""
    mock_model = MagicMock()
    mock_model.predict.return_value = [0.5]

    with patch("npc_engine.retrieval.cross_encoder_reranker._get_cross_encoder", return_value=mock_model):
        candidates = [{"id": "x", "score": 0.5, "payload": {"other_field": "value"}}]
        rerank("query", candidates)

    called_pairs = mock_model.predict.call_args[0][0]
    assert called_pairs[0] == ("query", "")
