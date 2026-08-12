"""
Module: tests.unit.scripts.test_check_dead_keywords
Layer: tests
Purpose: Unit tests for scripts/check_dead_keywords.py — flags keyword_none
         terms that never occur anywhere in a committed corpus (EVAL-P19.3).
Dependencies: pathlib, sys, pytest, check_dead_keywords
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_dead_keywords import (  # noqa: E402
    DeadKeyword,
    find_dead_keywords,
    format_report,
)


def _case(case_id: str, keywords: list[str], *, kind: str = "keyword_none") -> dict:
    """Build a minimal case dict with one keyword_none expectation."""
    return {"case_id": case_id, "expected": [{"kind": kind, "keywords": keywords}]}


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_keyword_never_present_in_corpus_is_flagged() -> None:
    """A keyword with zero corpus hits is a guaranteed pass — flag it."""
    cases = [_case("case_neg_example", ["never said this phrase"])]
    corpus = ["Nothing relevant here.", "Nor here."]

    dead = find_dead_keywords(cases, corpus)

    assert dead == [DeadKeyword(case_id="case_neg_example", keyword="never said this phrase")]


# ---------------------------------------------------------------------------
# Validation — the two measured examples from EVAL-P19.3
# ---------------------------------------------------------------------------


def test_thieves_guild_is_flagged_when_corpus_only_has_the_possessive() -> None:
    """'thieves guild' forbidden, corpus only ever writes "thieves' guild" —
    the exact measured EVAL-P19.3 example."""
    cases = [_case("case_neg_lira_no_trust_disclosure", ["thieves guild"])]
    corpus = ["The thieves' guild runs this district."] * 20

    dead = find_dead_keywords(cases, corpus)

    assert len(dead) == 1
    assert dead[0].keyword == "thieves guild"


def test_i_heard_is_flagged_when_corpus_only_has_ive_heard() -> None:
    """'i heard' forbidden, corpus only ever writes "I've heard" — the second
    measured EVAL-P19.3 example."""
    cases = [_case("case_neg_captain_sorn_no_hedging", ["i heard"])]
    corpus = ["I've heard the north is quiet these days."]

    dead = find_dead_keywords(cases, corpus)

    assert len(dead) == 1
    assert dead[0].keyword == "i heard"


# ---------------------------------------------------------------------------
# A keyword that does occur is never flagged
# ---------------------------------------------------------------------------


def test_keyword_present_in_corpus_is_not_flagged() -> None:
    cases = [_case("case_neg_example", ["stolen goods"])]
    corpus = ["I have no stolen goods here."]

    assert find_dead_keywords(cases, corpus) == []


def test_word_boundary_semantics_match_the_runner() -> None:
    """A single-word keyword that only occurs as a substring of a longer word
    is still dead — check_dead_keywords must use the same word-boundary rule
    as matchers.py, or it would under-report."""
    cases = [_case("case_neg_example", ["war"])]
    corpus = ["The warmth of the hearth was welcome."]

    dead = find_dead_keywords(cases, corpus)

    assert len(dead) == 1
    assert dead[0].keyword == "war"


# ---------------------------------------------------------------------------
# Non-keyword_none expectations are ignored
# ---------------------------------------------------------------------------


def test_non_keyword_none_expectations_are_ignored() -> None:
    cases = [_case("case_pos_example", ["never in corpus"], kind="keyword_any")]
    corpus = ["Anything at all."]

    assert find_dead_keywords(cases, corpus) == []


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------


def test_format_report_names_case_and_keyword() -> None:
    dead = [DeadKeyword(case_id="case_neg_x", keyword="never said")]
    text = format_report(dead)
    assert "case_neg_x" in text
    assert "never said" in text


def test_format_report_clean_corpus_says_none_found() -> None:
    text = format_report([])
    assert "No dead keyword" in text
