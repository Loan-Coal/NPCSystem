"""
Module: retrieval_panel
Layer: demo_game.ui
Purpose: RETRIEVAL right-panel tab — shows the retrieved context items
         (key, tier, text snippet) returned by GET /v1/admin/debug/retrieval,
         making the engine's grounded-memory moat visible to demo buyers.
         Data pushed from game_window via RightPanelRenderer.set_retrieval_payload().
Does NOT: make HTTP calls or hold mutable engine state.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

import pygame

from demo_game.constants import PALETTE

# ---------------------------------------------------------------------------
# Colour aliases
# ---------------------------------------------------------------------------

_CLR_BG = PALETTE["bg"]
_CLR_AMBER = PALETTE["amber"]
_CLR_WHITE = PALETTE["white"]
_CLR_GREY = PALETTE["grey"]
_CLR_BORDER = PALETTE["border"]

_CLR_MUTED = (100, 100, 120)
_CLR_VALUE = (180, 180, 200)
_CLR_NO_DATA = (80, 80, 100)
_CLR_KEY = PALETTE["amber"]
_CLR_TIER = (120, 160, 200)
_CLR_TOKENS = (100, 140, 100)

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

_PAD_X = 12
_PAD_Y = 12
_ROW_H = 48          # approximate height per context-item block
_MAX_TEXT_CHARS = 60  # characters shown of item text before truncation

_SECTION_HDR = "RETRIEVAL CONTEXT"
_EMPTY_HINT = "Run a dialogue turn to populate retrieval context"


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------


class RetrievalPanelWidget:
    """Panel showing the retrieved context items for the active NPC + query.

    Data is set via ``set_payload()``. Renders key/tier/text for each
    context item. Gracefully shows an empty-state hint when no data exists.

    Args:
        font_body: Body font used for section headers and token summary.
        font_label: Smaller monospace font for per-item rows.
    """

    def __init__(
        self,
        font_body: pygame.font.Font,
        font_label: pygame.font.Font,
    ) -> None:
        self._font_body = font_body
        self._font_label = font_label
        self._items: list[dict] = []
        self._total_tokens: int = 0
        self._npc_id: str = ""
        self._query: str = ""

    # ------------------------------------------------------------------
    # Data setter
    # ------------------------------------------------------------------

    def set_payload(self, payload: dict | None) -> None:
        """Replace the displayed retrieval payload.

        Args:
            payload: Parsed JSON from GET /v1/admin/debug/retrieval, matching
                     the DebugRetrievalResponse shape (npc_id, query,
                     context_items, total_tokens). Pass None or {} to clear.
        """
        if not payload:
            self._items = []
            self._total_tokens = 0
            self._npc_id = ""
            self._query = ""
            return
        self._items = list(payload.get("context_items") or [])
        self._total_tokens = int(payload.get("total_tokens") or 0)
        self._npc_id = str(payload.get("npc_id") or "")
        self._query = str(payload.get("query") or "")

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the retrieval panel inside rect.

        Args:
            surface: Target pygame surface.
            rect: Content area (below the tab header strip).
        """
        pygame.draw.rect(surface, _CLR_BG, rect)
        x = rect.x + _PAD_X
        y = rect.y + _PAD_Y

        y = self._draw_section_header(surface, x, y, rect)
        pygame.draw.line(
            surface, _CLR_BORDER,
            (rect.x + _PAD_X, y), (rect.right - _PAD_X, y),
        )
        y += 8

        if not self._items:
            _draw_no_data(surface, self._font_label, _EMPTY_HINT, _CLR_NO_DATA, rect)
            return

        for item in self._items:
            if y + _ROW_H > rect.bottom:
                break
            y = self._draw_item_row(surface, x, y, rect, item)
            pygame.draw.line(
                surface, _CLR_BORDER,
                (rect.x + _PAD_X, y - 2), (rect.right - _PAD_X, y - 2),
            )

    def _draw_section_header(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        rect: pygame.Rect,
    ) -> int:
        """Draw the section title and token summary; return y below."""
        hdr_surf = self._font_body.render(_SECTION_HDR, True, _CLR_AMBER)
        surface.blit(hdr_surf, (x, y))
        y += hdr_surf.get_height() + 2

        tokens_label = f"tokens: {self._total_tokens}  items: {len(self._items)}"
        if self._npc_id:
            tokens_label = f"{self._npc_id}  |  {tokens_label}"
        tok_surf = self._font_label.render(tokens_label, True, _CLR_TOKENS)
        surface.blit(tok_surf, (x, y))
        y += tok_surf.get_height() + 6
        return y

    def _draw_item_row(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        rect: pygame.Rect,
        item: dict,
    ) -> int:
        """Draw one context-item row; return y below the row."""
        key = str(item.get("key") or "")
        tier = str(item.get("tier") or "")
        text = str(item.get("text") or "")

        y = self._draw_key_tier_line(surface, x, y, key, tier)
        y = self._draw_text_line(surface, x, y, text)
        return y + 4

    def _draw_key_tier_line(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        key: str,
        tier: str,
    ) -> int:
        """Render key + tier badge on one line; return y below."""
        key_surf = self._font_label.render(key, True, _CLR_KEY)
        surface.blit(key_surf, (x, y))
        if tier:
            tier_label = f"[{tier}]"
            tier_surf = self._font_label.render(tier_label, True, _CLR_TIER)
            surface.blit(tier_surf, (x + key_surf.get_width() + 6, y))
        return y + key_surf.get_height() + 2

    def _draw_text_line(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        text: str,
    ) -> int:
        """Render a truncated snippet of the item text; return y below."""
        snippet = text[:_MAX_TEXT_CHARS]
        if len(text) > _MAX_TEXT_CHARS:
            snippet = snippet[:-1] + "…"
        txt_surf = self._font_label.render(snippet, True, _CLR_VALUE)
        surface.blit(txt_surf, (x, y))
        return y + txt_surf.get_height() + 2


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _draw_no_data(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    clr: tuple[int, int, int],
    rect: pygame.Rect,
) -> None:
    """Render hint text word-wrapped and centered inside rect.

    Args:
        surface: Target pygame surface.
        font: Font used for rendering.
        text: Hint text to display.
        clr: Text colour tuple.
        rect: Bounding rect to centre text within.
    """
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if font.size(trial)[0] <= rect.width - 2 * _PAD_X:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    total_h = len(lines) * font.get_linesize()
    start_y = rect.centery - total_h // 2
    for i, line in enumerate(lines):
        surf = font.render(line, True, clr)
        surface.blit(
            surf,
            (rect.centerx - surf.get_width() // 2, start_y + i * font.get_linesize()),
        )
