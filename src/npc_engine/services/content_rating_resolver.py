"""
Module: content_rating_resolver
Layer: services
Purpose: Resolves the effective content rating for a given world.
Does NOT: query Neo4j or call any I/O; per-world override is deferred (DEC-080).
Dependencies injected: default_rating (ContentRating) via __init__.
Dependencies: npc_engine.config
Used by: npc_engine.api.dependencies, npc_engine.engines.dialogue.dialogue_handler
"""

from __future__ import annotations

from npc_engine.config import ContentRating


class ContentRatingResolver:
    """Resolves the effective content rating for a given world.

    For S16.1 the global config rating is always returned.  Per-world override
    requires a graph schema decision (DEC-080) and is deferred.

    Args:
        default_rating: The global rating from Settings.CONTENT_RATING.
    """

    def __init__(self, default_rating: ContentRating) -> None:
        """Store the global default rating.

        Args:
            default_rating: Rating value from Settings.CONTENT_RATING.
        """
        self._default_rating = default_rating

    def resolve(self, world_id: str) -> ContentRating:
        """Return the effective rating for world_id.

        Currently always returns default_rating; per-world override is deferred
        to DEC-080.

        Args:
            world_id: The world node ID (unused until DEC-080 is resolved).

        Returns:
            The effective ContentRating for this world.
        """
        return self._default_rating
