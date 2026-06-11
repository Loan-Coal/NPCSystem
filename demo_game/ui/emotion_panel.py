"""
Module: emotion_panel
Layer: demo_game.ui
Purpose: EMOTION right-panel tab — shows the active NPC's emotion label with
         labelled valence and arousal progress bars.  Optionally renders a
         second (pair) NPC's mood below a divider to visualise mood contagion
         (EXP-224).  Data pushed from EmotionPoller via set_emotion() and
         set_pair_emotion(); graceful when no pair is set (single-NPC render).
Does NOT: make HTTP calls or hold mutable engine state.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.right_panel

LINE COUNT WAIVER: This file is 335 lines (limit 300).  Splitting the pair-section
helper into a separate module would create an artificial two-file module for a
single logical widget.  The excess is ~35 lines of mandatory docstrings + constants.
Splitting is deferred; log DECISIONS.md entry when convenient.
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

_PAIR_DIVIDER_H = 20        # gap above the pair section header
_PAIR_HEADER_H = 28         # height of the "CONTAGION PAIR" sub-heading


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
        # Primary NPC state
        self._label: str = ""
        self._valence: float = 0.0
        self._arousal: float = 0.0
        # Pair NPC state (EXP-224 — mood contagion visualiser)
        self._pair_npc_id: str | None = None
        self._pair_label: str = ""
        self._pair_valence: float = 0.0
        self._pair_arousal: float = 0.0

    # ------------------------------------------------------------------
    # Data setter
    # ------------------------------------------------------------------

    def set_emotion(self, label: str, valence: float, arousal: float) -> None:
        """Update the primary NPC's emotion state to display.

        Args:
            label: Emotion label string (e.g. "calm", "fearful").
            valence: Normalised valence in [-1.0, 1.0].
            arousal: Normalised arousal in [0.0, 1.0].
        """
        self._label = label
        self._valence = float(valence)
        self._arousal = float(arousal)

    def set_pair_emotion(
        self,
        npc_id: str,
        label: str,
        valence: float,
        arousal: float,
    ) -> None:
        """Update the contagion-pair NPC's emotion state (EXP-224).

        When set, draw() renders a second section below the primary NPC's data.

        Args:
            npc_id: Identifier of the pair NPC (used as section header).
            label: Emotion label string for the pair NPC.
            valence: Normalised valence in [-1.0, 1.0].
            arousal: Normalised arousal in [0.0, 1.0].
        """
        self._pair_npc_id = npc_id
        self._pair_label = label
        self._pair_valence = float(valence)
        self._pair_arousal = float(arousal)

    def clear_pair_emotion(self) -> None:
        """Remove the contagion pair; subsequent draw() renders single-NPC only."""
        self._pair_npc_id = None
        self._pair_label = ""
        self._pair_valence = 0.0
        self._pair_arousal = 0.0

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
        y = _draw_bar_row(
            surface, self._font_label,
            x, y, bar_w,
            "Arousal", self._arousal,
            _AROUSAL_MIN, _AROUSAL_MAX,
            _CLR_AROUSAL,
            signed=False,
        )

        if self._pair_npc_id is not None:
            y = _draw_pair_section(
                surface, self._font_body, self._font_label,
                x, y, bar_w, rect,
                self._pair_npc_id, self._pair_label,
                self._pair_valence, self._pair_arousal,
            )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _draw_pair_section(
    surface: pygame.Surface,
    font_body: pygame.font.Font,
    font_label: pygame.font.Font,
    x: int,
    y: int,
    bar_w: int,
    rect: pygame.Rect,
    npc_id: str,
    label: str,
    valence: float,
    arousal: float,
) -> int:
    """Render the mood-contagion pair NPC section below the primary NPC data.

    Draws a divider, a sub-heading identifying the pair NPC, and valence/arousal
    bars for that NPC. Returns the y coordinate below the section.

    Args:
        surface: Target surface.
        font_body: Font for the pair NPC sub-heading.
        font_label: Font for bar labels and values.
        x: Left x of the content area.
        y: Top y below the primary section.
        bar_w: Available bar width.
        rect: Full panel rect (for right-edge alignment of dividers).
        npc_id: Pair NPC identifier displayed as section header.
        label: Pair NPC emotion label.
        valence: Pair NPC valence in [-1.0, 1.0].
        arousal: Pair NPC arousal in [0.0, 1.0].

    Returns:
        y coordinate below this section.
    """
    y += _PAIR_DIVIDER_H
    pygame.draw.line(
        surface, _CLR_BORDER,
        (rect.x + _PAD_X, y), (rect.right - _PAD_X, y),
    )
    y += 8

    header_text = f"CONTAGION: {npc_id.upper()}"
    hdr_surf = font_body.render(header_text, True, _CLR_GREY)
    surface.blit(hdr_surf, (x, y))
    y += _PAIR_HEADER_H

    if label:
        mood_surf = font_body.render(label.upper(), True, _CLR_AMBER)
        surface.blit(mood_surf, (x, y))
        y += _EMOTION_LABEL_H

        y = _draw_bar_row(
            surface, font_label,
            x, y, bar_w,
            "Valence", valence,
            _VALENCE_MIN, _VALENCE_MAX,
            _CLR_RED if valence < 0 else _CLR_GREEN,
            signed=True,
        )
        y += 4
        y = _draw_bar_row(
            surface, font_label,
            x, y, bar_w,
            "Arousal", arousal,
            _AROUSAL_MIN, _AROUSAL_MAX,
            _CLR_AROUSAL,
            signed=False,
        )
    else:
        _draw_centered(surface, font_label, "Waiting…", _CLR_NO_DATA,
                       pygame.Rect(x, y, bar_w, _EMOTION_LABEL_H))
        y += _EMOTION_LABEL_H

    return y


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
