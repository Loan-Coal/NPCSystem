"""
context_relevance_engine.py - Re-export stub; implementation lives in retrieval/.
Layer: engines
Purpose: (auto-detected — review)

Does NOT: define any logic.

Dependencies injected: None.
"""

from npc_engine.retrieval.context_relevance_engine import (
    ContextRelevanceCandidate,
    MAX_COMPONENT_SCORE,
    MIN_COMPONENT_SCORE,
    rank_context_candidates,
    score_candidate,
)

__all__ = [
    "ContextRelevanceCandidate",
    "MAX_COMPONENT_SCORE",
    "MIN_COMPONENT_SCORE",
    "rank_context_candidates",
    "score_candidate",
]
