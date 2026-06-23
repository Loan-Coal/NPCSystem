"""
test_context_relevance_engine_v14.py - Unit tests for deterministic context relevance ranking.

Does NOT: execute retrieval or database queries.

Dependencies injected: none.
"""

import pytest

from npc_engine.engines.dialogue.context_relevance_engine import (
    ContextRelevanceCandidate,
    rank_context_candidates,
    score_candidate,
)
from npc_engine.retrieval.context import ContextItem
from npc_engine.schema.context_config_models import RelevanceWeights


def _weights() -> RelevanceWeights:
    return RelevanceWeights(
        recency=0.30,
        severity=0.20,
        proximity=0.20,
        relation=0.20,
        quest=0.10,
    )


def test_score_candidate_matches_weighted_formula() -> None:
    candidate = ContextRelevanceCandidate(
        node_id="event-1",
        node_type="event",
        item=ContextItem(key="event:1", text='{"summary":"x"}', tier="tierA", priority=10),
        recency=0.5,
        severity=0.4,
        proximity_hops=1,
        relation=0.3,
        quest=0.2,
    )

    score = score_candidate(candidate=candidate, weights=_weights(), max_proximity_hops=2)
    assert score == pytest.approx(0.41)


def test_rank_context_candidates_uses_tie_breaker_node_type_then_id() -> None:
    candidates = [
        ContextRelevanceCandidate(
            node_id="z-2",
            node_type="location",
            item=ContextItem(key="location:z-2", text="{}", tier="tierA", priority=1),
            recency=0.5,
            severity=0.0,
            proximity_hops=0,
            relation=0.0,
            quest=0.0,
        ),
        ContextRelevanceCandidate(
            node_id="a-1",
            node_type="character",
            item=ContextItem(key="character:a-1", text="{}", tier="tierA", priority=1),
            recency=0.5,
            severity=0.0,
            proximity_hops=0,
            relation=0.0,
            quest=0.0,
        ),
    ]

    ranked = rank_context_candidates(candidates=candidates, weights=_weights(), max_proximity_hops=2)
    assert [item.key for item in ranked] == ["character:a-1", "location:z-2"]


def test_score_candidate_zeroes_proximity_beyond_max_hops() -> None:
    candidate = ContextRelevanceCandidate(
        node_id="event-2",
        node_type="event",
        item=ContextItem(key="event:2", text='{"summary":"y"}', tier="tierB", priority=10),
        recency=0.0,
        severity=0.0,
        proximity_hops=9,
        relation=0.0,
        quest=0.0,
    )

    score = score_candidate(candidate=candidate, weights=_weights(), max_proximity_hops=2)
    assert score == 0.0


def test_rank_context_candidates_is_deterministic_across_input_order() -> None:
    baseline = [
        ContextRelevanceCandidate(
            node_id="b",
            node_type="event",
            item=ContextItem(key="event:b", text="{}", tier="tierA", priority=10),
            recency=0.2,
            severity=0.5,
            proximity_hops=1,
            relation=0.2,
            quest=0.0,
        ),
        ContextRelevanceCandidate(
            node_id="a",
            node_type="event",
            item=ContextItem(key="event:a", text="{}", tier="tierA", priority=10),
            recency=0.3,
            severity=0.5,
            proximity_hops=1,
            relation=0.2,
            quest=0.0,
        ),
    ]

    ranked_one = rank_context_candidates(candidates=baseline, weights=_weights(), max_proximity_hops=2)
    ranked_two = rank_context_candidates(candidates=list(reversed(baseline)), weights=_weights(), max_proximity_hops=2)

    assert [item.key for item in ranked_one] == [item.key for item in ranked_two]