"""
Module: investigation_panel
Layer: demo_game.ui
Purpose: INVESTIGATE right-panel tab — surfaces alibi/rumor contradictions
         from get_investigation(), each clue showing its graph provenance (source).
         Enables the player to solve crimes from graph contradictions.
         NOTE: The "discovered schemes" overlay is deferred to F2.3 (DEC-107).
Does NOT: make HTTP calls or hold mutable engine state.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

from typing import Callable

import pygame

from demo_game.constants import PALETTE

_CLR_BG = PALETTE["bg"]
_CLR_AMBER = PALETTE["amber"]
_CLR_WHITE = PALETTE["white"]
_CLR_GREY = PALETTE["grey"]
_CLR_GREEN = PALETTE["green"]
_CLR_RED = PALETTE["red"]
_CLR_BORDER = PALETTE["border"]

_CLR_MUTED = (100, 100, 120)
_CLR_NO_DATA = (80, 80, 100)
_CLR_VALUE = (180, 180, 200)
_CLR_SOURCE = (100, 160, 220)
_CLR_CONTRADICTION = (220, 130, 50)

_PAD_X = 12
_PAD_Y = 10
_ROW_H = 18
_BTN_H = 22
_BTN_W = 110
_MAX_CLUE_CHARS = 48
_MAX_SOURCE_CHARS = 36

_SECTION_ALIBI = "ALIBI CONTRADICTIONS"
_SECTION_RUMOR = "RUMOR CONTRADICTIONS"
_NO_DATA_MSG = "No investigation loaded"
_NO_EVENT_MSG = "Set event id to investigate"
_BTN_INVESTIGATE_LABEL = "[INVESTIGATE]"


class InvestigationPanelWidget:
    """Surfaces investigation contradictions with graph provenance.

    Call ``set_investigation()`` with the result of ``get_investigation()``.
    Call ``set_investigate_callback()`` to wire the [INVESTIGATE] button.

    Note: Discovered-schemes overlay is deferred to F2.3 (DEC-107 gating).

    Args:
        font_body: Body font for section headers.
        font_label: Smaller font for clue rows.
    """

    def __init__(
        self,
        font_body: pygame.font.Font,
        font_label: pygame.font.Font,
    ) -> None:
        self._font_body = font_body
        self._font_label = font_label
        self._investigation: dict | None = None
        self._event_id: str | None = None
        self._investigate_cb: Callable[[], None] | None = None
        self._investigate_btn_rect: pygame.Rect | None = None
        self._scroll_y: int = 0

    # ------------------------------------------------------------------
    # Data / callback setters
    # ------------------------------------------------------------------

    def set_investigation(self, data: dict | None) -> None:
        """Replace the displayed investigation payload.

        Args:
            data: Dict from get_investigation() with alibi_contradictions
                  and rumor_contradictions keys, or None to clear.
        """
        self._investigation = data
        self._scroll_y = 0

    def set_event_id(self, event_id: str | None) -> None:
        """Set the crime event id being investigated.

        Args:
            event_id: Event node ID, or None.
        """
        self._event_id = event_id

    def set_investigate_callback(self, cb: Callable[[], None]) -> None:
        """Register callback invoked when [INVESTIGATE] is clicked.

        Args:
            cb: Zero-arg callable.
        """
        self._investigate_cb = cb

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle MOUSEBUTTONDOWN (button click) and MOUSEWHEEL (scroll).

        Args:
            event: Pygame event to process.
        """
        if event.type == pygame.MOUSEWHEEL:
            self._scroll_y = max(0, self._scroll_y - event.y * 20)
            return
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self._investigate_btn_rect and self._investigate_btn_rect.collidepoint(event.pos):
            if self._investigate_cb:
                self._investigate_cb()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render alibi + rumor contradictions inside rect.

        Args:
            surface: Target pygame surface.
            rect: Content area (below the tab header strip).
        """
        pygame.draw.rect(surface, _CLR_BG, rect)

        x = rect.x + _PAD_X
        y = rect.y + _PAD_Y

        hdr_surf = self._font_body.render("INVESTIGATION", True, _CLR_AMBER)
        surface.blit(hdr_surf, (x, y))
        y += hdr_surf.get_height() + 4

        pygame.draw.line(
            surface, _CLR_BORDER,
            (rect.x + _PAD_X, y), (rect.right - _PAD_X, y),
        )
        y += 8

        content_bottom = rect.bottom - _BTN_H - _PAD_Y * 2
        clip = pygame.Rect(rect.x, y, rect.width, content_bottom - y)
        old_clip = surface.get_clip()
        surface.set_clip(clip)

        if self._investigation is None:
            msg = _NO_DATA_MSG if self._event_id is None else _NO_EVENT_MSG
            self._draw_centered_msg(surface, rect, msg)
        else:
            draw_y = y - self._scroll_y
            draw_y = self._draw_contradiction_section(
                surface, rect, x, draw_y,
                _SECTION_ALIBI,
                self._investigation.get("alibi_contradictions") or [],
            )
            draw_y = self._draw_contradiction_section(
                surface, rect, x, draw_y,
                _SECTION_RUMOR,
                self._investigation.get("rumor_contradictions") or [],
            )

        surface.set_clip(old_clip)

        btn_y = rect.bottom - _BTN_H - _PAD_Y
        self._investigate_btn_rect = self._draw_button(
            surface, x, btn_y, _BTN_W, _BTN_H,
            _BTN_INVESTIGATE_LABEL, PALETTE["panel"],
        )

    def _draw_contradiction_section(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        x: int,
        y: int,
        title: str,
        items: list[dict],
    ) -> int:
        """Draw a labelled section of contradictions; return y below section."""
        sec_surf = self._font_body.render(title, True, _CLR_CONTRADICTION)
        surface.blit(sec_surf, (x, y))
        y += sec_surf.get_height() + 4

        pygame.draw.line(
            surface, _CLR_BORDER,
            (rect.x + _PAD_X, y), (rect.right - _PAD_X, y),
        )
        y += 6

        if not items:
            no_surf = self._font_label.render("None found", True, _CLR_NO_DATA)
            surface.blit(no_surf, (x, y))
            y += _ROW_H + 4
            return y

        for item in items:
            y = self._draw_clue_row(surface, x, y, item)

        return y + 4

    def _draw_clue_row(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        item: dict,
    ) -> int:
        """Draw one clue row with content + source provenance; return y below."""
        clue_text = str(item.get("description") or item.get("clue") or item.get("text", ""))
        source = str(item.get("source") or item.get("source_id") or "")

        clue_trunc = clue_text[:_MAX_CLUE_CHARS] + (
            "…" if len(clue_text) > _MAX_CLUE_CHARS else ""
        )
        clue_surf = self._font_label.render(clue_trunc, True, _CLR_VALUE)
        surface.blit(clue_surf, (x, y))
        y += _ROW_H

        if source:
            src_trunc = source[:_MAX_SOURCE_CHARS] + (
                "…" if len(source) > _MAX_SOURCE_CHARS else ""
            )
            src_surf = self._font_label.render(f"  source: {src_trunc}", True, _CLR_SOURCE)
            surface.blit(src_surf, (x, y))
            y += _ROW_H

        y += 2
        return y

    def _draw_button(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        w: int,
        h: int,
        label: str,
        color: tuple[int, int, int],
    ) -> pygame.Rect:
        """Draw a simple text button; return its rect."""
        btn_rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(surface, color, btn_rect, border_radius=3)
        pygame.draw.rect(surface, _CLR_BORDER, btn_rect, width=1, border_radius=3)
        lbl_surf = self._font_label.render(label, True, _CLR_AMBER)
        surface.blit(lbl_surf, (
            btn_rect.centerx - lbl_surf.get_width() // 2,
            btn_rect.centery - lbl_surf.get_height() // 2,
        ))
        return btn_rect

    def _draw_centered_msg(
        self, surface: pygame.Surface, rect: pygame.Rect, msg: str
    ) -> None:
        """Render a centred informational message."""
        surf = self._font_label.render(msg, True, _CLR_NO_DATA)
        surface.blit(surf, (
            rect.centerx - surf.get_width() // 2,
            rect.centery - surf.get_height() // 2,
        ))
