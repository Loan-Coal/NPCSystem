"""
Module: test_matchers_keywords
Layer: test (unit)
Purpose: Unit tests for word-boundary keyword matching (EVAL-P19.2) — both
         the keyword_matching.py primitive and its wiring into matchers.py's
         keyword_any/keyword_all/keyword_none evaluators.
Dependencies: pytest, keyword_matching, matchers (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from keyword_matching import contains_keyword, is_single_word
from matchers import evaluate


def _resp(text: str) -> dict:
    return {"npc_response": text}


# ---------------------------------------------------------------------------
# is_single_word
# ---------------------------------------------------------------------------


def test_is_single_word_true_for_bare_word() -> None:
    assert is_single_word("graphic") is True


def test_is_single_word_false_for_phrase() -> None:
    assert is_single_word("thieves guild") is False


# ---------------------------------------------------------------------------
# contains_keyword — RED anchor
# ---------------------------------------------------------------------------


def test_single_word_keyword_does_not_match_inside_a_longer_word() -> None:
    """'graphic' must not match inside 'geographic' — the exact false
    positive that motivated EVAL-P19.2."""
    assert contains_keyword("geographic maps are useful.", "graphic") is False


def test_single_word_keyword_matches_as_a_whole_word() -> None:
    """'graphic' still matches when it appears as its own word."""
    assert contains_keyword("the scene was quite graphic.", "graphic") is True


def test_rumor_does_not_match_inside_rumors() -> None:
    assert contains_keyword("rumors spread fast.", "rumor") is False


def test_rumor_matches_as_its_own_word() -> None:
    assert contains_keyword("the rumor spread fast.", "rumor") is True


def test_multi_word_phrase_keeps_substring_semantics() -> None:
    """A multi-word phrase is not a single regex word and keeps plain
    substring matching — this must not regress under the word-boundary change."""
    assert contains_keyword("the thieves guild meets tonight.", "thieves guild") is True


def test_contains_keyword_does_no_case_folding_itself() -> None:
    """contains_keyword is case-sensitive — matchers.py lowercases both sides
    before calling it, matching its existing convention. A caller that skips
    that step gets a case-sensitive miss, not a silent case-insensitive match."""
    assert contains_keyword("hello world", "World") is False


# ---------------------------------------------------------------------------
# Wiring into matchers.py's keyword evaluators
# ---------------------------------------------------------------------------


def test_keyword_none_no_longer_trips_on_geographic() -> None:
    """keyword_none forbidding 'graphic' must pass on a response that only
    contains 'geographic' — the exact validation named by EVAL-P19.2."""
    ok, _ = evaluate(
        {"kind": "keyword_none", "keywords": ["graphic"]},
        _resp("These are geographic features of the region."),
    )
    assert ok is True


def test_keyword_none_still_trips_on_the_real_word() -> None:
    ok, _ = evaluate(
        {"kind": "keyword_none", "keywords": ["graphic"]},
        _resp("The description was rather graphic."),
    )
    assert ok is False


def test_keyword_any_word_boundary_applies() -> None:
    ok, _ = evaluate(
        {"kind": "keyword_any", "keywords": ["war", "peace"]},
        _resp("The warmth of the fire was welcome."),
    )
    assert ok is False, "'war' must not match inside 'warmth'"


def test_keyword_all_word_boundary_applies() -> None:
    ok, _ = evaluate(
        {"kind": "keyword_all", "keywords": ["war", "peace"]},
        _resp("There was war and peace both."),
    )
    assert ok is True


def test_keyword_none_multi_word_phrase_still_matches_via_substring() -> None:
    """Regression guard: multi-word forbidden phrases must keep working —
    EVAL-P19.2 only changes single-word semantics."""
    ok, _ = evaluate(
        {"kind": "keyword_none", "keywords": ["thieves guild"]},
        _resp("Word is the thieves guild runs this district."),
    )
    assert ok is False
