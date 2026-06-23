"""
Tests for ContentRatingResolver (S16.1).

All tests are pure unit tests with no I/O.
"""
from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from npc_engine.config import ContentRating, Settings
from npc_engine.services.content_rating_resolver import ContentRatingResolver


class _RatingModel(BaseModel):
    """Helper model to test ContentRating Literal validation."""

    rating: ContentRating


def test_resolve_returns_default_rating() -> None:
    resolver = ContentRatingResolver(default_rating="everyone")
    assert resolver.resolve(world_id="world_a") == "everyone"


def test_resolve_ignores_world_id() -> None:
    resolver = ContentRatingResolver(default_rating="teen")
    assert resolver.resolve(world_id="world_a") == resolver.resolve(world_id="world_b")


def test_content_rating_is_valid_literal() -> None:
    for valid in ("everyone", "teen", "mature"):
        assert _RatingModel(rating=valid).rating == valid
    with pytest.raises(ValidationError):
        _RatingModel(rating="adult")  # type: ignore[arg-type]


def test_settings_default_is_mature() -> None:
    settings = Settings(API_KEY_SECRET="test-key-minimum-16")
    assert settings.CONTENT_RATING == "mature"
