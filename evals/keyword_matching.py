"""
Module: keyword_matching
Layer: evals (eval harness — not part of src/)
Purpose: Word-boundary-aware keyword containment for the eval matchers. A bare
         substring check treats any single-word keyword as matching inside a
         longer word that happens to contain it — 'graphic' inside
         'geographic', 'rumor' inside 'rumors' — a false positive that
         inflates the guard battery's forbidden-keyword hit rate (EVAL-P19.2).
         Multi-word phrases keep plain substring semantics: a phrase is not a
         single regex "word", and substring matching is what tolerates its
         real variance (punctuation, possessives) across the corpus.
Dependencies: re, functools
Used by: matchers.py (_eval_keyword_any / _eval_keyword_all / _eval_keyword_none)
"""

from __future__ import annotations

import re
from functools import lru_cache

_KEYWORD_PATTERN_CACHE_SIZE: int = 256


def is_single_word(keyword: str) -> bool:
    """True if keyword has no internal whitespace.

    Word-boundary matching applies only to single-word terms — a multi-word
    phrase is not a single regex "word" and keeps substring semantics.

    Args:
        keyword: The keyword or phrase to check.
    Returns:
        True if keyword contains no whitespace once stripped.
    """
    return " " not in keyword.strip()


@lru_cache(maxsize=_KEYWORD_PATTERN_CACHE_SIZE)
def _word_boundary_pattern(keyword: str) -> re.Pattern[str]:
    """Compile (and cache) a word-boundary regex for one single-word keyword."""
    return re.compile(r"\b" + re.escape(keyword) + r"\b")


def contains_keyword(text: str, keyword: str) -> bool:
    """True if keyword is present in text under the applicable matching rule.

    Single-word keywords require a word boundary on both sides — 'graphic'
    no longer matches inside 'geographic'. Multi-word phrases keep plain
    substring matching. Both text and keyword are expected already
    lowercased, matching matchers.py's existing convention; this function
    does not itself lowercase either argument.

    Args:
        text: The (already lowercased) haystack.
        keyword: The (already lowercased) keyword or phrase to find.
    Returns:
        True if keyword is present under the applicable rule.
    """
    if is_single_word(keyword):
        return _word_boundary_pattern(keyword).search(text) is not None
    return keyword in text
