"""
Module: emotion_panel
Layer: demo_game.ui
Purpose: EMOTION right-panel tab — shows the active NPC's emotion label with
         labelled valence and arousal progress bars.
         Data pushed from EmotionPoller via RightPanelRenderer.set_emotion().
Does NOT: make HTTP calls or hold mutable engine state.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

import pygame

from demo_game.constants import PALETTE

_CLR_BG = PALETTE["bg"]
_CLR_PANEL = PALETTE["panel"]
_CLR_AMBER = PALETTE["amber"]
_CLR_WHITE = PALETTE["white"]
_CLR_GREY = PALETTE["grey"]
_CLR_GREEN = PALETTE["green"]
_CLR_RED = PALETTE["red"]
_CLR_BORDER = PALETTE["border"]

_CLR_BAR_BG = (40, 40, 55)
_CLR_AROUSAL = (100, 140, 220)
_CLR_MUTED = (100, 100, 120)
_CLR_VALUE = (180, 180, 200)
_CLR_NO_DATA = (80, 80, 100)

_PAD_X = 12
_PAD_Y = 16
_LABEL_COL_W = 72      # fixed width for row labels ("Valence:", "Arousal:")
_BAR_H = 14
_BAR_ROW_H = 22        # height of one bar row (bar + gap)
_EMOTION_LABEL_H = 32  # height of the large emotion-name header

_VALENCE_MIN = -1.0
_VALENCE_MAX = 1.0
_AROUSAL_MIN = 0.0
_AROUSAL_MAX = 1.0


class EmotionPanelWidget:
    """Full right-panel EMOTION view with labelled valence and arousal bars.

    Call ``set_emotion()`` after each EmotionPoller tick; the widget is
    stateless between draw calls (no scroll, no interaction).

    Args:
        font_body: Body font for the emotion-name label.
        font_label: Smaller font for row labels and value text.
    """

    def __init__(
        self,
        font_body: pygame.font.Font,
        font_label: pygame.font.Font,
    ) -> None:
        self._font_body = font_body
        self._font_label = font_label
        self._label: str = ""
        self._valence: float = 0.0
        self._arousal: float = 0.0

    # ------------------------------------------------------------------
    # Data setter
    # ------------------------------------------------------------------

    def set_emotion(self, label: str, valence: float, arousal: float) -> None:
        """Update the emotion state to display.

        Args:
            label: Emotion label string (e.g. "calm", "fearful").
            valence: Normalised valence in [-1.0, 1.0].
            arousal: Normalised arousal in [0.0, 1.0].
        """
        self._label = label
        self._valence = float(valence)
        self._arousal = float(arousal)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the emotion panel inside rect.

        Args:
            surface: Target pygame surface.
            rect: Content area (below the tab header strip).
        """
        pygame.draw.rect(surface, _CLR_BG, rect)
        if not self._label:
            _draw_centered(surface, self._font_body, "No emotion data", _CLR_NO_DATA, rect)
            return

        x = rect.x + _PAD_X
        y = rect.y + _PAD_Y

        # Large emotion-name header
        lbl_surf = self._font_body.render(self._label.upper(), True, _CLR_AMBER)
        surface.blit(lbl_surf, (x, y))
        y += _EMOTION_LABEL_H

        # Divider
        pygame.draw.line(
            surface, _CLR_BORDER,
            (rect.x + _PAD_X, y), (rect.right - _PAD_X, y),
        )
        y += 8

        bar_w = rect.width - 2 * _PAD_X
        y = _draw_bar_row(
            surface, self._font_label,
            x, y, bar_w,
            "Valence", self._valence,
            _VALENCE_MIN, _VALENCE_MAX,
            _CLR_RED if self._valence < 0 else _CLR_GREEN,
            signed=True,
        )
        y += 4
        _draw_bar_row(
            surface, self._font_label,
            x, y, bar_w,
            "Arousal", self._arousal,
            _AROUSAL_MIN, _AROUSAL_MAX,
            _CLR_AROUSAL,
            signed=False,
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _draw_bar_row(
    surface: pygame.Surface,
    font: pygame.font.Font,
    x: int,
    y: int,
    total_w: int,
    label: str,
    value: float,
    v_min: float,
    v_max: float,
    bar_clr: tuple[int, int, int],
    *,
    signed: bool,
) -> int:
    """Draw one labelled progress bar row and return the y position below it.

    Args:
        surface: Target surface.
        font: Font for labels and values.
        x: Left x of the row.
        y: Top y of the row.
        total_w: Total available width for the row.
        label: Row label string (e.g. "Valence").
        value: Current value to display.
        v_min: Minimum of the value range.
        v_max: Maximum of the value range.
        bar_clr: Fill colour for the progress bar.
        signed: If True, format value with a leading + or -.

    Returns:
        y coordinate below this row.
    """
    val_str = f"{value:+.2f}" if signed else f"{value:.2f}"
    lbl_surf = font.render(f"{label}:", True, _CLR_MUTED)
    val_surf = font.render(val_str, True, _CLR_VALUE)

    bar_x = x + _LABEL_COL_W
    val_x = x + total_w - val_surf.get_width()
    bar_w = val_x - bar_x - 8

    surface.blit(lbl_surf, (x, y))
    surface.blit(val_surf, (val_x, y))

    bar_rect = pygame.Rect(bar_x, y + 2, max(bar_w, 0), _BAR_H)
    pygame.draw.rect(surface, _CLR_BAR_BG, bar_rect, border_radius=3)

    ratio = (value - v_min) / (v_max - v_min) if v_max != v_min else 0.0
    ratio = max(0.0, min(1.0, ratio))
    filled_w = int(bar_w * ratio)
    if filled_w > 0:
        pygame.draw.rect(
            surface, bar_clr,
            pygame.Rect(bar_x, y + 2, filled_w, _BAR_H),
            border_radius=3,
        )

    return y + _BAR_ROW_H


def _draw_centered(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    clr: tuple[int, int, int],
    rect: pygame.Rect,
) -> None:
    """Render text centred inside rect."""
    surf = font.render(text, True, clr)
    surface.blit(surf, (
        rect.centerx - surf.get_width() // 2,
        rect.centery - surf.get_height() // 2,
    ))
