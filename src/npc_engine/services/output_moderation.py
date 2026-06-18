"""
Module: output_moderation
Layer: services
Purpose: Post-generation check that flags NPC output violating the content rating ceiling.
Does NOT: raise exceptions or call the LLM; returns a boolean flag for the handler.
Dependencies injected: blocklist (frozenset[str]) via __init__.
Dependencies: npc_engine.config, npc_engine.services.input_moderation (BLOCKLISTS)
Used by: npc_engine.engines.dialogue.dialogue_handler, npc_engine.api.dependencies
"""

from __future__ import annotations

import re

from npc_engine.config import ContentRating
from npc_engine.services.input_moderation import BLOCKLISTS


class OutputModerationService:
    """Post-generation check: flags NPC output that violates the content ceiling.

    Uses the same blocklist mechanism as InputModerationService. Returns a bool
    rather than raising so the handler can substitute a canned response.
    The regex is compiled once in __init__ for O(n) repeated checks.

    Args:
        blocklist: Lower-cased terms forbidden in NPC output under the effective rating.
    """

    def __init__(self, blocklist: frozenset[str]) -> None:
        """Compile the blocklist into a single regex for fast repeated matching.

        Args:
            blocklist: Forbidden terms (case-insensitive word-boundary scan).
        """
        if blocklist:
            escaped = sorted(re.escape(term) for term in blocklist)
            self._pattern: re.Pattern[str] | None = re.compile(
                r"\b(" + "|".join(escaped) + r")\b",
                re.IGNORECASE,
            )
        else:
            self._pattern = None

    def is_over_ceiling(self, npc_response: str) -> bool:
        """Return True if npc_response contains any blocked term.

        Args:
            npc_response: The raw NPC response string from the LLM.

        Returns:
            True when the response violates the ceiling; False otherwise.
        """
        if self._pattern is None:
            return False
        return bool(self._pattern.search(npc_response))


def build_output_moderation_service(rating: ContentRating) -> OutputModerationService:
    """Construct OutputModerationService for the given content rating ceiling.

    Args:
        rating: Effective content ceiling from Settings.CONTENT_RATING.

    Returns:
        OutputModerationService wired with the appropriate blocklist.
    """
    return OutputModerationService(blocklist=BLOCKLISTS[rating])
