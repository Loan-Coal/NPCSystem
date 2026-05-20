"""
context_relevance_engine.py - Deterministic context relevance scoring and ranking.

Does NOT: fetch graph/vector data.

Dependencies injected: RelevanceWeights.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from npc_engine.retrieval.context_merger import ContextItem
from npc_engine.schema.context_config_models import RelevanceWeights


MIN_COMPONENT_SCORE = 0.0
MAX_COMPONENT_SCORE = 1.0


class ContextRelevanceCandidate(BaseModel):
    """Scorable candidate bound to one context item."""

    node_id: str = Field(min_length=1)
    node_type: str = Field(min_length=1)
    item: ContextItem
    recency: float = Field(ge=MIN_COMPONENT_SCORE, le=MAX_COMPONENT_SCORE)
    severity: float = Field(ge=MIN_COMPONENT_SCORE, le=MAX_COMPONENT_SCORE)
    proximity_hops: int = Field(ge=0)
    relation: float = Field(ge=MIN_COMPONENT_SCORE, le=MAX_COMPONENT_SCORE)
    quest: float = Field(ge=MIN_COMPONENT_SCORE, le=MAX_COMPONENT_SCORE)

    model_config = ConfigDict(frozen=True)


def score_candidate(
    *,
    candidate: ContextRelevanceCandidate,
    weights: RelevanceWeights,
    max_proximity_hops: int,
) -> float:
    """Compute weighted deterministic relevance score for one candidate.

    Args:
        candidate: The scored candidate holding component values.
        weights: Configured relevance weight coefficients.
        max_proximity_hops: Maximum graph-hop distance used for proximity normalization.

    Returns:
        A non-negative float representing the combined relevance score.
    """

    proximity_score = _proximity_score(
        proximity_hops=candidate.proximity_hops,
        max_proximity_hops=max_proximity_hops,
    )
    return (
        weights.recency * candidate.recency
        + weights.severity * candidate.severity
        + weights.proximity * proximity_score
        + weights.relation * candidate.relation
        + weights.quest * candidate.quest
    )


def rank_context_candidates(
    *,
    candidates: list[ContextRelevanceCandidate],
    weights: RelevanceWeights,
    max_proximity_hops: int,
) -> list[ContextItem]:
    """Return context items ranked by score with deterministic tie-break rules.

    Args:
        candidates: Unordered list of scored candidates to rank.
        weights: Configured relevance weight coefficients.
        max_proximity_hops: Maximum graph-hop distance for proximity scoring.

    Returns:
        List of ContextItem values in descending relevance order, with priority
        fields rewritten to reflect rank position (1000 down to 1).
    """

    scored = [
        (
            score_candidate(candidate=candidate, weights=weights, max_proximity_hops=max_proximity_hops),
            candidate,
        )
        for candidate in candidates
    ]
    scored.sort(
        key=lambda entry: (
            -entry[0],
            entry[1].node_type,
            entry[1].node_id,
            entry[1].item.key,
        )
    )

    ranked_items: list[ContextItem] = []
    for index, (_, candidate) in enumerate(scored):
        ranked_items.append(
            candidate.item.model_copy(
                update={
                    "priority": max(1, 1000 - index),
                }
            )
        )
    return ranked_items


def _proximity_score(*, proximity_hops: int, max_proximity_hops: int) -> float:
    """Convert graph-hop distance into normalized proximity score in [0, 1]."""

    if max_proximity_hops <= 0:
        return 1.0 if proximity_hops == 0 else 0.0
    if proximity_hops > max_proximity_hops:
        return 0.0
    return 1.0 - (proximity_hops / max_proximity_hops)
