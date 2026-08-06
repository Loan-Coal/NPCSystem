"""
Module: test_knowledge_scorer
Layer: test (unit)
Purpose: Tests for evals/knowledge_scorer.py — pure unpropagated-event-reference scorer.
         Zero I/O; all tests use inline frozensets and fixture text strings.
Dependencies: pytest, knowledge_scorer (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from knowledge_scorer import KnowledgeScore, unpropagated_references

# ---------------------------------------------------------------------------
# Shared fixtures — demo world events (from CLAUDE.md)
# ---------------------------------------------------------------------------

_EVENT_VOCAB: frozenset[str] = frozenset({"northern_war_begins"})

# old_henryk does NOT know northern_war_begins (2-hop distorted gossip target,
# not a direct KNOWS_ABOUT recipient in the demo world).
_HENRYK_KNOWN: frozenset[str] = frozenset()

# captain_sorn has a direct KNOWS_ABOUT northern_war_begins edge (per CLAUDE.md).
_SORN_KNOWN: frozenset[str] = frozenset({"northern_war_begins"})

_FIXTURE_TEXT = "northern_war_begins has changed everything in the north."

# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_event_not_in_known_set_is_flagged() -> None:
    """Event in vocabulary but absent from NPC known set counts as a violation."""
    result = unpropagated_references(_FIXTURE_TEXT, _EVENT_VOCAB, _HENRYK_KNOWN)
    assert result.violations == 1
    assert result.references == 1


# ---------------------------------------------------------------------------
# Demo-world contrast: captain_sorn (direct KNOWS_ABOUT)
# ---------------------------------------------------------------------------


def test_known_event_yields_zero_violations() -> None:
    """Event present in NPC known set is not a violation even when mentioned."""
    result = unpropagated_references(_FIXTURE_TEXT, _EVENT_VOCAB, _SORN_KNOWN)
    assert result.violations == 0
    assert result.references == 1


# ---------------------------------------------------------------------------
# No-mention baseline
# ---------------------------------------------------------------------------


def test_no_event_mention_no_violations() -> None:
    """Text with no event IDs → references 0, violations 0, rate 0.0."""
    text = "It was a quiet evening by the fire."
    result = unpropagated_references(text, _EVENT_VOCAB, _HENRYK_KNOWN)
    assert result.references == 0
    assert result.violations == 0
    assert result.rate == 0.0


# ---------------------------------------------------------------------------
# Rate arithmetic
# ---------------------------------------------------------------------------


def test_rate_is_zero_when_all_known() -> None:
    """All references in known set → violations 0, rate 0.0."""
    vocab = frozenset({"event_a", "event_b"})
    known = frozenset({"event_a", "event_b"})
    text = "event_a happened, then event_b followed."
    result = unpropagated_references(text, vocab, known)
    assert result.references == 2
    assert result.violations == 0
    assert result.rate == 0.0


def test_rate_is_one_when_all_violations() -> None:
    """All references unknown → rate 1.0."""
    vocab = frozenset({"event_a"})
    known: frozenset[str] = frozenset()
    text = "event_a surprised everyone."
    result = unpropagated_references(text, vocab, known)
    assert result.references == 1
    assert result.violations == 1
    assert result.rate == 1.0


def test_rate_rounded_to_three_decimals() -> None:
    """Rate is rounded to 3 decimal places: 1/3 → 0.333."""
    vocab = frozenset({"event_a", "event_b", "event_c"})
    known = frozenset({"event_b", "event_c"})
    text = "event_a caused event_b and event_c."
    result = unpropagated_references(text, vocab, known)
    assert result.references == 3
    assert result.violations == 1
    assert result.rate == pytest.approx(0.333, abs=1e-9)


# ---------------------------------------------------------------------------
# Case-insensitivity
# ---------------------------------------------------------------------------


def test_matching_is_case_insensitive() -> None:
    """Event IDs are matched case-insensitively in the text."""
    text = "NORTHERN_WAR_BEGINS shocked the villagers."
    result = unpropagated_references(text, _EVENT_VOCAB, _HENRYK_KNOWN)
    assert result.references == 1
    assert result.violations == 1


# ---------------------------------------------------------------------------
# Events not in vocabulary are ignored
# ---------------------------------------------------------------------------


def test_event_not_in_vocab_is_ignored() -> None:
    """An event present in npc_known_event_ids but absent from event_vocabulary
    does not affect scoring — only vocabulary events are searched for."""
    # event_x is in known set but NOT in vocabulary → not searched for
    vocab = frozenset({"event_a"})
    known = frozenset({"event_x"})
    text = "event_a is connected to event_x somehow."
    result = unpropagated_references(text, vocab, known)
    # Only event_a is searched; it is not in known set → 1 violation
    assert result.references == 1
    assert result.violations == 1


# ---------------------------------------------------------------------------
# Multiple occurrences of the same event
# ---------------------------------------------------------------------------


def test_multiple_occurrences_each_counted() -> None:
    """Each occurrence of an unknown event in the text is counted separately."""
    text = "northern_war_begins started long ago. northern_war_begins still rages."
    result = unpropagated_references(text, _EVENT_VOCAB, _HENRYK_KNOWN)
    assert result.references == 2
    assert result.violations == 2


# ---------------------------------------------------------------------------
# KnowledgeScore model
# ---------------------------------------------------------------------------


def test_knowledge_score_is_frozen() -> None:
    """KnowledgeScore is immutable after construction."""
    score = KnowledgeScore(references=1, violations=0, rate=0.0)
    with pytest.raises(Exception):
        score.references = 99  # type: ignore[misc]
