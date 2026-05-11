"""
test_context_scoring.py - Unit tests for context relevance scoring helpers.

Does NOT: call graph, vector store, or LLM services.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from npc_engine.retrieval.context_merger import ContextItem
from npc_engine.retrieval.context_scoring import (
    _extract_recency_score,
    _extract_relation_score,
    _extract_severity_score,
    _infer_proximity_hops,
    _normalize_ratio,
    _quest_score,
    rank_tier_items,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(*, key: str = "character:npc_1", text: str = "{}", tier: str = "tierA", priority: int = 50) -> ContextItem:
    return ContextItem(key=key, text=text, tier=tier, priority=priority)  # type: ignore[arg-type]


def _make_llm_config(*, max_proximity_hops: int = 3) -> MagicMock:
    cfg = MagicMock()
    cfg.max_proximity_hops = max_proximity_hops
    cfg.prompt_schema_version = "v1"
    cfg.compression_prompt_version = "v1"
    weights = MagicMock()
    cfg.relevance_weights = weights
    return cfg


# ---------------------------------------------------------------------------
# _normalize_ratio
# ---------------------------------------------------------------------------


def test_normalize_ratio_clamps_above_one():
    assert _normalize_ratio(1.5) == 1.0


def test_normalize_ratio_clamps_below_zero():
    assert _normalize_ratio(-0.5) == 0.0


def test_normalize_ratio_passes_through_valid():
    assert _normalize_ratio(0.75) == 0.75


def test_normalize_ratio_boundary_zero():
    assert _normalize_ratio(0.0) == 0.0


def test_normalize_ratio_boundary_one():
    assert _normalize_ratio(1.0) == 1.0


# ---------------------------------------------------------------------------
# _quest_score
# ---------------------------------------------------------------------------


def test_quest_score_key_contains_quest():
    item = _make_item(key="quest:q_001")
    assert _quest_score(item=item) == 1.0


def test_quest_score_key_no_quest():
    item = _make_item(key="character:npc_1")
    assert _quest_score(item=item) == 0.0


def test_quest_score_case_insensitive():
    item = _make_item(key="QUEST:upper")
    assert _quest_score(item=item) == 1.0


# ---------------------------------------------------------------------------
# _infer_proximity_hops
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key,expected", [
    ("character:npc_1", 0),
    ("relation:npc_1:npc_2", 0),
    ("location:market", 1),
    ("nearby_npcs:npc_1", 1),
    ("event:battle_01", 1),
    ("session:turn_3", 0),
])
def test_infer_proximity_hops_known_prefixes(key: str, expected: int):
    assert _infer_proximity_hops(key, max_proximity_hops=3) == expected


def test_infer_proximity_hops_rag_exceeds_max():
    assert _infer_proximity_hops("rag:lore_doc_01", max_proximity_hops=2) == 3


def test_infer_proximity_hops_unknown_falls_back_to_max():
    assert _infer_proximity_hops("unknown_type:xyz", max_proximity_hops=4) == 4


# ---------------------------------------------------------------------------
# _extract_severity_score
# ---------------------------------------------------------------------------


def test_extract_severity_score_numeric():
    payload = {"severity": 50}
    assert _extract_severity_score(payload) == pytest.approx(0.5)


def test_extract_severity_score_zero():
    payload = {"severity": 0}
    assert _extract_severity_score(payload) == 0.0


def test_extract_severity_score_max():
    payload = {"severity": 100}
    assert _extract_severity_score(payload) == pytest.approx(1.0)


def test_extract_severity_score_missing_field():
    assert _extract_severity_score({}) == 0.0


def test_extract_severity_score_non_numeric_field():
    assert _extract_severity_score({"severity": "high"}) == 0.0


# ---------------------------------------------------------------------------
# _extract_recency_score
# ---------------------------------------------------------------------------


def test_extract_recency_score_very_recent_event():
    recent = datetime.now(timezone.utc).isoformat()
    payload = {"occurred_at": recent}
    score = _extract_recency_score(payload)
    assert score > 0.9


def test_extract_recency_score_old_event_scores_low():
    old = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat()
    payload = {"occurred_at": old}
    score = _extract_recency_score(payload)
    assert score == 0.0


def test_extract_recency_score_missing_fields():
    assert _extract_recency_score({}) == 0.0


def test_extract_recency_score_invalid_timestamp_skipped():
    payload = {"occurred_at": "not-a-date", "updated_at": datetime.now(timezone.utc).isoformat()}
    score = _extract_recency_score(payload)
    assert score > 0.9


def test_extract_recency_score_uses_first_valid_field():
    recent = datetime.now(timezone.utc).isoformat()
    old = (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat()
    payload = {"occurred_at": recent, "updated_at": old}
    score = _extract_recency_score(payload)
    assert score > 0.9


# ---------------------------------------------------------------------------
# _extract_relation_score
# ---------------------------------------------------------------------------


def test_extract_relation_score_tier_b_uses_vector_score():
    item = _make_item(tier="tierB", key="character:npc_1")
    score = _extract_relation_score(item=item, vector_scores={"character:npc_1": 0.85})
    assert score == pytest.approx(0.85)


def test_extract_relation_score_tier_b_missing_key_returns_zero():
    item = _make_item(tier="tierB", key="character:npc_1")
    score = _extract_relation_score(item=item, vector_scores={})
    assert score == 0.0


def test_extract_relation_score_tier_a_uses_priority():
    item = _make_item(tier="tierA", priority=80)
    score = _extract_relation_score(item=item, vector_scores={})
    assert score == pytest.approx(0.8)


def test_extract_relation_score_tier_a_priority_clamped():
    item = _make_item(tier="tierA", priority=200)
    score = _extract_relation_score(item=item, vector_scores={})
    assert score == 1.0


# ---------------------------------------------------------------------------
# rank_tier_items
# ---------------------------------------------------------------------------


def test_rank_tier_items_returns_list():
    items = [_make_item(key="character:npc_1"), _make_item(key="quest:q_01")]
    cfg = _make_llm_config()
    with patch("npc_engine.retrieval.context_scoring.rank_context_candidates", return_value=items) as mock_rank:
        result = rank_tier_items(items=items, llm_config=cfg, vector_scores={})
    assert result == items
    mock_rank.assert_called_once()


def test_rank_tier_items_empty_list():
    cfg = _make_llm_config()
    with patch("npc_engine.retrieval.context_scoring.rank_context_candidates", return_value=[]):
        result = rank_tier_items(items=[], llm_config=cfg, vector_scores={})
    assert result == []
