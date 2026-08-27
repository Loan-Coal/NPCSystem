"""
Module: tests.unit.evals.test_variance_scorer
Layer: tests
Purpose: Unit tests for evals/variance_scorer.py — EVAL-P25.4's deterministic
         contextual-variance metric. The maintainer's stated goal is "replies should be
         incredibly varied based on context and situation"; this scorer measures that
         over response strings alone, with no judge and therefore no kappa tax.
Dependencies: pytest, variance_scorer
Used by: make test / make check (pytest discovery)
"""

from __future__ import annotations

import pytest

from variance_scorer import (
    DIRECTIONAL_DELTA_THRESHOLD,
    MIN_RESPONSES_FOR_PAIRWISE,
    InsufficientResponsesError,
    contrast,
    jaccard_distance,
    normalize_tokens,
    pairwise_dissimilarity,
)

# Five responses that differ only in the state each NPC is in — the shape a
# contextual-variance case produces: one player_message, N NPCs, N answers.
_VARIED = (
    "The northern war has emptied my cellars and my purse alike.",
    "Bark from the northwood is what I need, and none arrives.",
    "My ledger says one thing; the dockside manifest says another entirely.",
    "The garrison holds the south gate, whatever the rumours claim.",
    "I keep the temple neutral. That is my whole occupation.",
)

# What a state-blind engine emits: the same sentence, cosmetically reworded.
_FLAT = (
    "Times are hard, traveller, and I could not say more than that.",
    "Times are hard, traveller, and I could not say more than that.",
    "Times are hard, traveller, and I could not say more than that.",
)


# ---------------------------------------------------------------------------
# RED anchor — a state-blind engine must score near zero, a varied one near one
# ---------------------------------------------------------------------------


def test_identical_responses_score_zero_dissimilarity() -> None:
    """The defect this metric exists to catch: one answer for every context."""
    score = pairwise_dissimilarity(_FLAT)

    assert score.mean_dissimilarity == pytest.approx(0.0)
    assert score.max_dissimilarity == pytest.approx(0.0)
    assert score.n_pairs == 3


def test_state_differentiated_responses_score_high_dissimilarity() -> None:
    """Five NPCs answering from five different states share almost no content tokens."""
    score = pairwise_dissimilarity(_VARIED)

    assert score.mean_dissimilarity > 0.8
    assert score.n_pairs == 10


def test_the_varied_set_outscores_the_flat_set() -> None:
    """The ordering is the claim. If this ever inverts the metric is measuring noise."""
    assert pairwise_dissimilarity(_VARIED).mean_dissimilarity > pairwise_dissimilarity(_FLAT).mean_dissimilarity


# ---------------------------------------------------------------------------
# The measure itself
# ---------------------------------------------------------------------------


def test_jaccard_distance_is_symmetric_and_bounded() -> None:
    """Bounded [0, 1] and symmetric — the two properties a dissimilarity must have."""
    a, b = "the war in the north", "a fire in the market"

    assert jaccard_distance(a, b) == pytest.approx(jaccard_distance(b, a))
    assert 0.0 <= jaccard_distance(a, b) <= 1.0
    assert jaccard_distance(a, a) == pytest.approx(0.0)
    assert jaccard_distance("alpha beta", "gamma delta") == pytest.approx(1.0)


def test_distance_ignores_case_and_punctuation() -> None:
    """Surface form is not content: the same words must not read as different content."""
    assert jaccard_distance("The war! In the north.", "the WAR in the north") == pytest.approx(0.0)


def test_two_empty_responses_are_maximally_dissimilar_not_identical() -> None:
    """An engine that says nothing has demonstrated no variance — never score it 0.

    0/0 is undefined and the tempting default (identical, distance 0) would make a
    silent engine look like a consistent one. It is unmeasured, so it scores 1.0.
    """
    assert jaccard_distance("", "") == pytest.approx(1.0)
    assert jaccard_distance("", "the war in the north") == pytest.approx(1.0)


def test_normalize_tokens_is_a_pure_word_split() -> None:
    """No stopword list: the docstring's argument is that function words cancel in the
    contrast, so the tokenizer carries no vocabulary to calibrate."""
    assert normalize_tokens("The war, in the North!") == frozenset({"the", "war", "in", "north"})


# ---------------------------------------------------------------------------
# The contrast — this is what makes the number attributable to CONTEXT
# ---------------------------------------------------------------------------


def test_contrast_separates_sampling_noise_from_contextual_variance() -> None:
    """Control: one NPC, one state, resampled. Treatment: N NPCs in differing states.

    Lexical variety alone proves nothing — sampling temperature produces that for free.
    The delta over a matched control is what attributes the variance to context.
    """
    control = (
        "Times are hard, traveller, and I could not say much more.",
        "Times are hard, friend, and I could not say a great deal more.",
        "Hard times, traveller. I could not say much more than that.",
    )
    result = contrast(control=control, treatment=_VARIED)

    assert result.control.mean_dissimilarity < result.treatment.mean_dissimilarity
    assert result.delta > DIRECTIONAL_DELTA_THRESHOLD
    assert result.meets_directional_gate is True


def test_contrast_fails_the_gate_when_context_changes_nothing() -> None:
    """A state-blind engine: the treatment group is no more varied than the control."""
    result = contrast(control=_VARIED, treatment=_FLAT)

    assert result.delta < 0
    assert result.meets_directional_gate is False


# ---------------------------------------------------------------------------
# Boundaries
# ---------------------------------------------------------------------------


def test_a_single_response_cannot_be_scored() -> None:
    """One response has no pair. That is unmeasured, not zero variance."""
    with pytest.raises(InsufficientResponsesError):
        pairwise_dissimilarity(("only one",))

    assert MIN_RESPONSES_FOR_PAIRWISE == 2


def test_scoring_is_order_independent() -> None:
    """A pure function of the multiset of responses — shuffling must not move the score."""
    forward = pairwise_dissimilarity(_VARIED).mean_dissimilarity
    backward = pairwise_dissimilarity(tuple(reversed(_VARIED))).mean_dissimilarity

    assert forward == pytest.approx(backward)
