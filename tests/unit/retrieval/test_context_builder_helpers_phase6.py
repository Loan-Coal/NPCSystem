"""
test_context_builder_helpers_phase6.py - Unit tests for Phase 6 helper additions.

Does NOT: execute I/O.
"""

from __future__ import annotations

import pytest

from npc_engine.retrieval.context import (
    expand_query,
    keyword_overlap,
    rerank_by_keyword,
)


# ---------------------------------------------------------------------------
# keyword_overlap
# ---------------------------------------------------------------------------


def test_keyword_overlap_exact_match():
    assert keyword_overlap("the guild leader is corrupt", "guild leader corrupt") == 1.0


def test_keyword_overlap_partial():
    score = keyword_overlap("the guild leader is corrupt", "leader merchant")
    assert 0.0 < score < 1.0


def test_keyword_overlap_no_match():
    assert keyword_overlap("the guild leader is corrupt", "dragon fire magic") == 0.0


def test_keyword_overlap_short_query_returns_zero():
    # Single-token queries are degenerate — always return 0.0
    assert keyword_overlap("yes of course", "yes") == 0.0


def test_keyword_overlap_empty_query():
    assert keyword_overlap("some text", "") == 0.0


def test_keyword_overlap_empty_text():
    assert keyword_overlap("", "guild leader") == 0.0


# ---------------------------------------------------------------------------
# expand_query
# ---------------------------------------------------------------------------


def test_expand_query_no_history():
    assert expand_query("Where is the blacksmith?", []) == "Where is the blacksmith?"


def test_expand_query_one_turn_no_expansion():
    result = expand_query("What did he do?", ["player: Tell me about the guild"])
    assert result == "What did he do?"


def test_expand_query_two_turns_prepends():
    turns = ["player: Tell me about the guild", "npc: It is corrupt"]
    result = expand_query("What happened next?", turns)
    assert "Tell me about the guild" in result
    assert "It is corrupt" in result
    assert result.endswith("What happened next?")


def test_expand_query_strips_speaker_prefix():
    turns = ["player: Find the merchant", "npc: He left town"]
    result = expand_query("Where did he go?", turns)
    assert "player:" not in result
    assert "npc:" not in result


def test_expand_query_uses_last_two_turns_only():
    turns = [
        "player: turn 1",
        "npc: turn 2",
        "player: turn 3",
        "npc: turn 4",
        "player: turn 5",
    ]
    result = expand_query("new message", turns)
    assert "turn 4" in result
    assert "turn 5" in result
    assert "turn 1" not in result
    assert "turn 2" not in result
    assert "turn 3" not in result


# ---------------------------------------------------------------------------
# rerank_by_keyword
# ---------------------------------------------------------------------------


def test_rerank_by_keyword_raises_most_relevant():
    items = [
        {"content": "The dragon guards the treasure", "id": "1"},
        {"content": "The guild leader knows the merchant", "id": "2"},
        {"content": "Someone stole the merchant's gold", "id": "3"},
    ]
    query = "guild merchant gold"
    result = rerank_by_keyword(items, "content", query, top_k=2)
    ids = [r["id"] for r in result]
    assert "1" not in ids  # dragon item is irrelevant
    assert len(result) == 2


def test_rerank_by_keyword_top_k_respected():
    items = [{"content": "a b c", "id": str(i)} for i in range(10)]
    result = rerank_by_keyword(items, "content", "a b c d", top_k=3)
    assert len(result) == 3


def test_rerank_by_keyword_empty_list():
    assert rerank_by_keyword([], "content", "query", top_k=3) == []


def test_rerank_by_keyword_missing_field_scores_zero():
    items = [
        {"summary": "relevant guild info", "id": "1"},
        {"content": "guild leader speaks", "id": "2"},
    ]
    # Field "content" exists for id=2 but not id=1 (uses "" fallback)
    result = rerank_by_keyword(items, "content", "guild leader", top_k=2)
    assert result[0]["id"] == "2"
