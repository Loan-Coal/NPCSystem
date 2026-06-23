"""
Module: player_model_panel
Layer: demo_game.ui
Purpose: PLAYER MODEL right-panel tab — shows what the focused NPC perceives
         about the player (perceived_trust and perceived_intent).
         Data pushed via RightPanelRenderer.set_player_model().
Does NOT: make HTTP calls or hold mutable engine state.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

import pygame

from demo_game.constants import PALETTE

_CLR_BG = PALETTE["bg"]
_CLR_AMBER = PALETTE["amber"]
_CLR_WHITE = PALETTE["white"]
_CLR_GREY = PALETTE["grey"]
_CLR_GREEN = PALETTE["green"]
_CLR_RED = PALETTE["red"]
_CLR_BORDER = PALETTE["border"]

_CLR_BAR_BG = (40, 40, 55)
_CLR_MUTED = (100, 100, 120)
_CLR_VALUE = (180, 180, 200)
_CLR_NO_DATA = (80, 80, 100)

_PAD_X = 12
_PAD_Y = 12
_BAR_H = 10
_TRUST_MAX = 100
_SECTION_HDR = "PLAYER MODEL"
_LABEL_TRUST = "perceived_trust"
_LABEL_INTENT = "perceived_intent"
_NO_DATA_MSG = "No player model yet"


def _trust_colour(trust: int) -> tuple[int, int, int]:
    """Return bar fill colour based on trust level."""
    if trust >= 70:
        return _CLR_GREEN
    if trust >= 40:
        return _CLR_AMBER
    return _CLR_RED


class PlayerModelPanelWidget:
    """Shows what the focused NPC perceives about the player.

    Displays perceived_trust as a progress bar and perceived_intent as a text
    badge. When no model is available (404 or not yet polled) renders a
    graceful "no data" placeholder.

    Call ``set_model()`` after each NpcPlayerModelPoller tick. Call with
    ``None`` to clear.

    Args:
        font_body: Body font for the section header.
        font_label: Smaller font for row content.
    """

    def __init__(
        self,
        font_body: pygame.font.Font,
        font_label: pygame.font.Font,
    ) -> None:
        self._font_body = font_body
        self._font_label = font_label
        self._model: dict | None = None

    # ------------------------------------------------------------------
    # Data setter
    # ------------------------------------------------------------------

    def set_model(self, model: dict | None) -> None:
        """Replace the displayed player-model snapshot.

        Args:
            model: Dict with at minimum ``perceived_trust`` and
                   ``perceived_intent`` keys, or None to clear.
        """
        self._model = model

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the player-model panel inside rect.

        Args:
            surface: Target pygame surface.
            rect: Content area (below the tab header strip).
        """
        pygame.draw.rect(surface, _CLR_BG, rect)
        x = rect.x + _PAD_X
        y = rect.y + _PAD_Y

        hdr_surf = self._font_body.render(_SECTION_HDR, True, _CLR_AMBER)
        surface.blit(hdr_surf, (x, y))
        y += hdr_surf.get_height() + 6

        pygame.draw.line(
            surface, _CLR_BORDER,
            (rect.x + _PAD_X, y), (rect.right - _PAD_X, y),
        )
        y += 8

        if self._model is None:
            self._draw_no_data(surface, rect)
            return

        y = self._draw_trust_row(surface, x, y, rect.width - 2 * _PAD_X)
        y += 10
        self._draw_intent_row(surface, x, y)

    def _draw_trust_row(
        self, surface: pygame.Surface, x: int, y: int, bar_total_w: int
    ) -> int:
        """Draw the perceived_trust label + bar; return y below the row."""
        trust = int(self._model.get("perceived_trust", 0))  # type: ignore[union-attr]
        bar_clr = _trust_colour(trust)

        lbl_surf = self._font_label.render(_LABEL_TRUST, True, _CLR_MUTED)
        surface.blit(lbl_surf, (x, y))

        val_surf = self._font_label.render(str(trust), True, _CLR_VALUE)
        val_x = x + bar_total_w - val_surf.get_width()
        surface.blit(val_surf, (val_x, y))

        bar_x = x + lbl_surf.get_width() + 6
        bar_w = val_x - bar_x - 6
        bar_rect = pygame.Rect(bar_x, y + 3, max(bar_w, 0), _BAR_H)
        pygame.draw.rect(surface, _CLR_BAR_BG, bar_rect, border_radius=3)

        ratio = max(0.0, min(1.0, trust / _TRUST_MAX))
        filled_w = int(bar_w * ratio)
        if filled_w > 0:
            pygame.draw.rect(
                surface, bar_clr,
                pygame.Rect(bar_x, y + 3, filled_w, _BAR_H),
                border_radius=3,
            )

        return y + _BAR_H + 8

    def _draw_intent_row(self, surface: pygame.Surface, x: int, y: int) -> None:
        """Draw the perceived_intent label + value badge."""
        intent = str(self._model.get("perceived_intent", "unknown"))  # type: ignore[union-attr]

        lbl_surf = self._font_label.render(_LABEL_INTENT, True, _CLR_MUTED)
        surface.blit(lbl_surf, (x, y))

        intent_surf = self._font_label.render(intent, True, _CLR_AMBER)
        surface.blit(intent_surf, (x + lbl_surf.get_width() + 10, y))

    def _draw_no_data(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render a centred 'no data' message."""
        surf = self._font_label.render(_NO_DATA_MSG, True, _CLR_NO_DATA)
        surface.blit(surf, (
            rect.centerx - surf.get_width() // 2,
            rect.centery - surf.get_height() // 2,
        ))
