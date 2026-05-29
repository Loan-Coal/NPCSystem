"""
Module: gossip_chain
Layer: demo_game.ui
Purpose: Renders the Sorn→Mira→Henryk gossip distortion chain in the CHAIN tab.
         Shows each NPC's distorted knowledge with a distortion percentage.
         Colour-coded: white (0%), amber (1–30%), red (31%+).
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

import pygame

from demo_game.constants import NPC_DISPLAY_NAMES, PALETTE

_ARROW = "  ↓  "
_EMPTY_LINES = ["No chain data.", "Run: make demo-seed"]
_SUMMARY_MAX_CHARS = 55  # truncation limit for distorted_summary snippets


def _distortion_colour(level: float) -> tuple[int, int, int]:
    """Map a distortion level [0.0, 1.0] to a display colour."""
    if level <= 0.0:
        return PALETTE["white"]
    if level <= 0.30:
        return PALETTE["amber"]
    return PALETTE["red"]


class GossipChainWidget:
    """Renders the KNOWS_ABOUT distortion chain for a target event.

    Displays each NPC who KNOWS_ABOUT the event, ordered by distortion level,
    with their distorted summary snippet. Designed for the CHAIN right-panel tab.

    Args:
        font_body: 14px monospace font for NPC names and summaries.
        font_label: 12px monospace font for distortion percentages and arrows.
    """

    def __init__(
        self,
        font_body: pygame.font.Font,
        font_label: pygame.font.Font,
    ) -> None:
        self._font_body = font_body
        self._font_label = font_label
        self._edges: list[dict] = []

    def set_chain(self, edges: list[dict]) -> None:
        """Update the chain with a fresh edge list, sorted by distortion_level.

        Args:
            edges: List of edge dicts from ``get_graph_edges("KNOWS_ABOUT", ...)``.
                   Expected fields: ``src_id``, ``distortion_level``,
                   ``distorted_summary``.
        """
        self._edges = sorted(
            edges,
            key=lambda e: float(e.get("distortion_level", 0.0)),
        )

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the chain onto surface within rect.

        Args:
            surface: Target pygame surface.
            rect: Bounding rect for the chain view.
        """
        pygame.draw.rect(surface, PALETTE["bg"], rect)
        if not self._edges:
            self._draw_empty(surface, rect)
        else:
            self._draw_chain(surface, rect)

    # ------------------------------------------------------------------
    # Private rendering helpers
    # ------------------------------------------------------------------

    def _draw_empty(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        lh = self._font_body.get_linesize()
        y = rect.centery - (len(_EMPTY_LINES) * lh) // 2
        for line in _EMPTY_LINES:
            txt = self._font_body.render(line, True, PALETTE["amber"])
            surface.blit(txt, (rect.centerx - txt.get_width() // 2, y))
            y += lh

    def _draw_chain(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        x = rect.x + 12
        y = rect.y + 12
        body_lh = self._font_body.get_linesize()
        label_lh = self._font_label.get_linesize()

        for i, edge in enumerate(self._edges):
            src_id = edge.get("src_id", "?")
            level = float(edge.get("distortion_level", 0.0))
            summary = str(edge.get("distorted_summary") or "")
            colour = _distortion_colour(level)
            pct = int(round(level * 100))

            # NPC name + distortion percentage on one line
            name = NPC_DISPLAY_NAMES.get(src_id, src_id)
            name_surf = self._font_body.render(f"[{name}]", True, colour)
            surface.blit(name_surf, (x, y))

            pct_surf = self._font_label.render(f"  ({pct}%)", True, colour)
            surface.blit(pct_surf, (x + name_surf.get_width(), y + (body_lh - label_lh) // 2))
            y += body_lh + 2

            # Truncated distorted summary snippet
            snippet = summary[:_SUMMARY_MAX_CHARS] + ("…" if len(summary) > _SUMMARY_MAX_CHARS else "")
            if snippet:
                snip_surf = self._font_label.render(snippet, True, PALETTE["grey"])
                surface.blit(snip_surf, (x + 8, y))
                y += label_lh + 4

            # Arrow between nodes (not after last)
            if i < len(self._edges) - 1:
                arrow_surf = self._font_label.render(_ARROW, True, PALETTE["grey"])
                surface.blit(arrow_surf, (x, y))
                y += label_lh + 6
