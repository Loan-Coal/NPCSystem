"""
Module: scheme_board_panel
Layer: demo_game.ui
Purpose: INTRIGUE right-panel tab — shows the focused NPC's schemes (covert goal,
         hidden vs discovered, and the covert steps that have manifested). Data
         pushed via RightPanelRenderer.set_schemes().
Does NOT: make HTTP calls or hold mutable engine state.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

import pygame

from demo_game.constants import PALETTE

_CLR_BG = PALETTE["bg"]
_CLR_AMBER = PALETTE["amber"]
_CLR_GREY = PALETTE["grey"]
_CLR_GREEN = PALETTE["green"]
_CLR_RED = PALETTE["red"]
_CLR_BORDER = PALETTE["border"]

_CLR_MUTED = (100, 100, 120)
_CLR_VALUE = (180, 180, 200)
_CLR_NO_DATA = (80, 80, 100)
_CLR_HIDDEN = (150, 130, 90)

_PAD_X = 12
_PAD_Y = 12
_STEP_INDENT = 16
_ROW_GAP = 6
_SCHEME_GAP = 12
_SECTION_HDR = "INTRIGUE"
_NO_DATA_MSG = "No schemes known"
_BADGE_DISCOVERED = "[DISCOVERED]"
_BADGE_HIDDEN = "[HIDDEN]"
_STEP_DONE = "✓"
_STEP_PENDING = "•"


class SchemeBoardPanelWidget:
    """Shows the focused NPC's schemes and their covert steps.

    Each scheme renders a status badge (discovered vs hidden), its covert goal,
    and the ordered steps that have manifested. When the NPC has no schemes (or
    none polled yet) a graceful placeholder is shown.

    Call ``set_schemes()`` after each NpcSchemesPoller tick.

    Args:
        font_body: Body font for the section header + scheme goals.
        font_label: Smaller font for badges and step rows.
    """

    def __init__(
        self,
        font_body: pygame.font.Font,
        font_label: pygame.font.Font,
    ) -> None:
        self._font_body = font_body
        self._font_label = font_label
        self._schemes: list[dict] = []

    # ------------------------------------------------------------------
    # Data setter
    # ------------------------------------------------------------------

    def set_schemes(self, schemes: list[dict] | None) -> None:
        """Replace the displayed scheme list.

        Args:
            schemes: List of scheme dicts (scheme_id, goal, status, discovered,
                steps), or None to clear.
        """
        self._schemes = list(schemes) if schemes else []

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the intrigue board inside rect.

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
            surface, _CLR_BORDER, (x, y), (rect.right - _PAD_X, y)
        )
        y += 8

        if not self._schemes:
            self._draw_no_data(surface, rect)
            return

        for scheme in self._schemes:
            y = self._draw_scheme(surface, x, y, scheme, rect.bottom)
            if y >= rect.bottom:
                break

    def _draw_scheme(
        self, surface: pygame.Surface, x: int, y: int, scheme: dict, bottom: int
    ) -> int:
        """Draw one scheme (badge + goal + steps); return y below the block."""
        discovered = bool(scheme.get("discovered"))
        badge = _BADGE_DISCOVERED if discovered else _BADGE_HIDDEN
        badge_clr = _CLR_GREEN if discovered else _CLR_HIDDEN
        badge_surf = self._font_label.render(badge, True, badge_clr)
        surface.blit(badge_surf, (x, y))

        goal = str(scheme.get("goal", "?"))
        goal_surf = self._font_body.render(goal, True, _CLR_VALUE)
        surface.blit(goal_surf, (x + badge_surf.get_width() + 8, y))
        y += goal_surf.get_height() + _ROW_GAP

        for step in scheme.get("steps", []):
            if y >= bottom:
                break
            y = self._draw_step(surface, x + _STEP_INDENT, y, step)
        return y + _SCHEME_GAP

    def _draw_step(
        self, surface: pygame.Surface, x: int, y: int, step: dict
    ) -> int:
        """Draw one covert step row; return y below the row."""
        marker = _STEP_DONE if step.get("completed") else _STEP_PENDING
        order = step.get("step_order", "?")
        summary = str(step.get("summary") or "(covert step)")
        text = f"{marker} {order}. {summary}"
        surf = self._font_label.render(text, True, _CLR_MUTED)
        surface.blit(surf, (x, y))
        return y + surf.get_height() + _ROW_GAP

    def _draw_no_data(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render a centred 'no schemes' message."""
        surf = self._font_label.render(_NO_DATA_MSG, True, _CLR_NO_DATA)
        surface.blit(surf, (
            rect.centerx - surf.get_width() // 2,
            rect.centery - surf.get_height() // 2,
        ))
