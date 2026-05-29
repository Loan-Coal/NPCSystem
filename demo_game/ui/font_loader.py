"""
Module: font_loader
Layer: demo_game.ui
Purpose: Singleton TTF font loader with graceful fallback to pygame default.
Dependencies: pygame, pathlib
Used by: demo_game.ui.game_window
"""
from __future__ import annotations

from pathlib import Path

import pygame


class FontLoader:
    """Singleton cache for TTF fonts. Falls back to pygame default on FileNotFoundError."""

    _cache: dict[int, pygame.font.Font] = {}
    _FONT_PATH: Path = Path(__file__).parent.parent / "assets/fonts/JetBrainsMono-Regular.ttf"

    @classmethod
    def get(cls, size: int) -> pygame.font.Font:
        """Return a cached font at the given pixel size."""
        if size not in cls._cache:
            try:
                cls._cache[size] = pygame.font.Font(str(cls._FONT_PATH), size)
            except FileNotFoundError:
                cls._cache[size] = pygame.font.Font(None, size)
        return cls._cache[size]

    @classmethod
    def _clear_cache(cls) -> None:
        """Clear the font cache. Used in tests only."""
        cls._cache.clear()
