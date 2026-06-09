"""
Module: input_moderation
Layer: services
Purpose: Checks player input against the effective content rating ceiling before LLM call.
Does NOT: call the LLM or query Neo4j.
Dependencies injected: blocklist (frozenset[str]) and rating (str) via __init__.
Dependencies: npc_engine.config, npc_engine.utils.errors
Used by: npc_engine.engines.dialogue.dialogue_handler, npc_engine.api.dependencies
"""

from __future__ import annotations

import re

from npc_engine.config import ContentRating
from npc_engine.utils.errors import ContentRatingViolationError

# Conservative blocklists per content ceiling.
# "mature" is empty — no restrictions (preserves all existing behaviour).
# Terms are lower-cased; the compiled pattern uses IGNORECASE for hot-path efficiency.
_EVERYONE_BLOCKED_TERMS: frozenset[str] = frozenset(
    {"murder", "gore", "pornography", "rape", "torture", "mutilate", "beheading", "snuff"}
)
_TEEN_BLOCKED_TERMS: frozenset[str] = frozenset(
    {"pornography", "rape", "snuff", "mutilate", "beheading"}
)

BLOCKLISTS: dict[str, frozenset[str]] = {
    "everyone": _EVERYONE_BLOCKED_TERMS,
    "teen": _TEEN_BLOCKED_TERMS,
    "mature": frozenset(),
}


class InputModerationService:
    """Checks player input against the effective content rating ceiling.

    Raises ContentRatingViolationError on rejection; returns None on pass.
    The blocklist and rating are injected at construction time for testability.
    The regex is compiled once in __init__ for an O(n) hot path.

    Args:
        blocklist: Lower-cased terms forbidden under the effective rating.
        rating: Human-readable name of the ceiling (stored in raised errors).
    """

    def __init__(self, blocklist: frozenset[str], rating: str) -> None:
        """Compile the blocklist into a single regex for fast repeated matching.

        Args:
            blocklist: Forbidden terms (case-insensitive word-boundary scan).
            rating: Content rating label stored in ContentRatingViolationError.
        """
        self._rating = rating
        if blocklist:
            escaped = sorted(re.escape(term) for term in blocklist)
            self._pattern: re.Pattern[str] | None = re.compile(
                r"\b(" + "|".join(escaped) + r")\b",
                re.IGNORECASE,
            )
        else:
            self._pattern = None

    def check(self, player_message: str, player_id: str) -> None:
        """Raise ContentRatingViolationError if message contains a blocked term.

        Args:
            player_message: The raw player input string.
            player_id: Used to populate the error for structured logging.

        Raises:
            ContentRatingViolationError: When any blocked term is found.
        """
        if self._pattern is None:
            return
        if self._pattern.search(player_message):
            raise ContentRatingViolationError(player_id=player_id, rating=self._rating)


def build_input_moderation_service(rating: ContentRating) -> InputModerationService:
    """Construct InputModerationService for the given content rating ceiling.

    Args:
        rating: Effective content ceiling from Settings.CONTENT_RATING.

    Returns:
        InputModerationService wired with the appropriate blocklist.
    """
    return InputModerationService(blocklist=BLOCKLISTS[rating], rating=rating)
