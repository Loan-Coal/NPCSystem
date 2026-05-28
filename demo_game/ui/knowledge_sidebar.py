"""
Module: knowledge_sidebar
Layer: demo_game.ui
Purpose: Two-column gossip knowledge diff widget. Left column: what an NPC knows
         (potentially distorted). Right column: ground truth from the Event node.
         Colour-coded by distortion level. No HTTP, no engine imports.
Dependencies: pygame, demo_game.ui.widgets (_wrap_text)
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import pygame

from demo_game.ui.widgets import _wrap_text

# ---------------------------------------------------------------------------
# Colour palette — matches widgets.py
# ---------------------------------------------------------------------------
_CLR_AMBER = (200, 160, 80)    # distorted value highlight
_CLR_WHITE = (220, 220, 220)   # matching / ground truth text
_CLR_DIM = (130, 130, 140)     # missing field placeholder
_CLR_PANEL = (28, 28, 36)
_CLR_DIVIDER = (60, 60, 80)
_CLR_HEADER_BG = (22, 22, 32)
_CLR_COL_HEADER = (160, 160, 180)

_HEADER_H = 28    # NPC name strip
_COL_HDR_H = 20   # "WHAT X KNOWS" / "GROUND TRUTH" strip
_ROW_PAD = 8      # vertical padding inside each event row
_COL_PAD = 8      # horizontal padding inside each column


class KnowledgeSidebarWidget:
    """Side-by-side gossip knowledge diff widget.

    Displays one row per KNOWS_ABOUT edge, comparing what the NPC believes
    against the ground-truth Event node. Distorted fields are highlighted amber.

    Args:
        font: Main body font.
        label_font: Smaller font for column headers and field labels.
    """

    def __init__(
        self,
        font: pygame.font.Font,
        label_font: pygame.font.Font,
    ) -> None:
        self._font = font
        self._label_font = label_font
        self._npc_name: str = ""
        self._pairs: list[tuple[dict, dict]] = []
        self._scroll_px: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_data(
        self,
        npc_display_name: str,
        pairs: list[tuple[dict, dict]],
    ) -> None:
        """Replace displayed data and reset scroll to top.

        Args:
            npc_display_name: Human-readable NPC name for the header.
            pairs: List of (edge_props, event_props) tuples from the fetcher.
        """
        self._npc_name = npc_display_name
        self._pairs = list(pairs)
        self._scroll_px = 0

    def clear(self) -> None:
        """Clear all data and reset scroll."""
        self._npc_name = ""
        self._pairs = []
        self._scroll_px = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle scroll-wheel events.

        Args:
            event: Pygame event to inspect.
        """
        if event.type == pygame.MOUSEWHEEL:
            self._scroll_px = max(0, self._scroll_px - event.y * self._font.get_linesize())

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the sidebar onto ``surface`` at ``rect``.

        Args:
            surface: Target pygame Surface.
            rect: Bounding rectangle within ``surface``.
        """
        pygame.draw.rect(surface, _CLR_PANEL, rect, border_radius=4)

        y = rect.y

        # --- NPC name header strip ---
        hdr_rect = pygame.Rect(rect.x, y, rect.width, _HEADER_H)
        pygame.draw.rect(surface, _CLR_HEADER_BG, hdr_rect)
        if self._npc_name:
            title = f"{self._npc_name.upper()} — Knowledge vs Ground Truth"
        else:
            title = "Select an NPC to inspect knowledge"
        title_surf = self._label_font.render(title, True, _CLR_AMBER)
        surface.blit(title_surf, (rect.x + _COL_PAD, y + (_HEADER_H - title_surf.get_height()) // 2))
        y += _HEADER_H

        if not self._pairs:
            msg = self._font.render("No KNOWS_ABOUT edges found.", True, _CLR_DIM)
            surface.blit(msg, (rect.x + _COL_PAD, y + 12))
            return

        col_w = (rect.width - 3) // 2  # 1px divider + 2px gutter

        # --- Column headers ---
        col_hdr_rect = pygame.Rect(rect.x, y, rect.width, _COL_HDR_H)
        pygame.draw.rect(surface, _CLR_HEADER_BG, col_hdr_rect)

        left_lbl = self._label_font.render("WHAT THIS NPC KNOWS", True, _CLR_COL_HEADER)
        right_lbl = self._label_font.render("GROUND TRUTH", True, _CLR_COL_HEADER)
        surface.blit(left_lbl, (rect.x + _COL_PAD, y + (_COL_HDR_H - left_lbl.get_height()) // 2))
        right_x = rect.x + col_w + 3
        surface.blit(right_lbl, (right_x + _COL_PAD, y + (_COL_HDR_H - right_lbl.get_height()) // 2))
        y += _COL_HDR_H

        # 1px vertical divider line (drawn once for the full content area)
        divider_x = rect.x + col_w + 1
        content_bottom = rect.y + rect.height
        pygame.draw.line(surface, _CLR_DIVIDER, (divider_x, y), (divider_x, content_bottom))

        # --- Scrollable event rows ---
        clip_rect = pygame.Rect(rect.x, y, rect.width, rect.height - (y - rect.y))
        clip = surface.subsurface(clip_rect)
        clip.fill(_CLR_PANEL)

        max_col_w = col_w - _COL_PAD * 2
        line_h = self._font.get_linesize()
        lbl_h = self._label_font.get_linesize()

        # Pre-compute rows so we can compute total height for scroll
        rows = [self._build_row(edge, event, max_col_w) for edge, event in self._pairs]
        total_h = sum(r["height"] for r in rows)

        draw_y = -self._scroll_px
        for row in rows:
            self._draw_row(clip, row, col_w, draw_y, max_col_w, line_h, lbl_h)
            draw_y += row["height"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _classify_row(self, edge: dict, event: dict) -> str:
        """Classify a (edge, event) pair for diff colouring.

        Returns:
            'matching'  — distortion_level == 0
            'missing'   — distortion_level > 0 but distorted_summary is None
            'distorted' — distortion_level > 0 and distorted_summary is not None
        """
        level = edge.get("distortion_level", 0) or 0
        if level == 0:
            return "matching"
        distorted = edge.get("distorted_summary")
        if distorted is None:
            return "missing"
        return "distorted"

    def _build_row(self, edge: dict, event: dict, max_col_w: int) -> dict:
        """Pre-compute wrapped lines and pixel height for one event row.

        Args:
            edge: KNOWS_ABOUT edge property dict.
            event: Event node property dict.
            max_col_w: Available pixel width for text in one column.

        Returns:
            Dict with keys: edge, event, classification, left_lines, right_lines, height.
        """
        classification = self._classify_row(edge, event)

        event_name = event.get("name", event.get("id", "—"))
        event_summary = event.get("summary", "—")

        if classification == "distorted":
            left_summary = edge.get("distorted_summary") or "—"
        elif classification == "missing":
            left_summary = "—"
        else:
            left_summary = event_summary

        knowledge_tag = edge.get("knowledge_state", "?")
        distortion_pct = edge.get("distortion_level", 0) or 0
        left_meta = f"[{knowledge_tag}  dist={distortion_pct}]"

        left_name_lines = _wrap_text(self._font, event_name, max_col_w)
        left_summary_lines = _wrap_text(self._font, left_summary, max_col_w)
        left_meta_lines = _wrap_text(self._label_font, left_meta, max_col_w)

        right_name_lines = _wrap_text(self._font, event_name, max_col_w)
        right_summary_lines = _wrap_text(self._font, event_summary, max_col_w)

        lh = self._font.get_linesize()
        llh = self._label_font.get_linesize()
        row_h = (
            len(left_name_lines) * lh
            + max(len(left_summary_lines), len(right_summary_lines)) * lh
            + len(left_meta_lines) * llh
            + _ROW_PAD * 2 + 4  # top/bottom padding + separator
        )

        return {
            "edge": edge,
            "event": event,
            "classification": classification,
            "left_name_lines": left_name_lines,
            "left_summary_lines": left_summary_lines,
            "left_meta_lines": left_meta_lines,
            "right_name_lines": right_name_lines,
            "right_summary_lines": right_summary_lines,
            "height": row_h,
        }

    def _draw_row(
        self,
        clip: pygame.Surface,
        row: dict,
        col_w: int,
        draw_y: int,
        max_col_w: int,
        line_h: int,
        lbl_h: int,
    ) -> None:
        """Render one event row onto the clip surface.

        Args:
            clip: Subsurface clipped to the scrollable content area.
            row: Pre-computed row dict from _build_row.
            col_w: Pixel width of one column (excluding divider).
            draw_y: Current Y offset within clip (may be negative when scrolled).
            max_col_w: Available pixel width for text.
            line_h: Body font line height.
            lbl_h: Label font line height.
        """
        h = row["height"]
        clip_h = clip.get_height()
        # Skip entirely off-screen rows
        if draw_y + h < 0 or draw_y >= clip_h:
            return

        classification = row["classification"]
        left_colour = _CLR_AMBER if classification == "distorted" else (
            _CLR_DIM if classification == "missing" else _CLR_WHITE
        )
        right_colour = _CLR_WHITE

        left_x = _COL_PAD
        right_x = col_w + 3 + _COL_PAD

        cy = draw_y + _ROW_PAD

        # Event name (both columns always white — it's the same name)
        for line in row["left_name_lines"]:
            if 0 <= cy < clip_h:
                s = self._font.render(line, True, _CLR_WHITE)
                clip.blit(s, (left_x, cy))
            cy += line_h

        # Right column name (rendered in parallel; track separately)
        right_cy = draw_y + _ROW_PAD
        for line in row["right_name_lines"]:
            if 0 <= right_cy < clip_h:
                s = self._font.render(line, True, right_colour)
                clip.blit(s, (right_x, right_cy))
            right_cy += line_h

        # Align summaries to same vertical start
        summary_start = draw_y + _ROW_PAD + len(row["left_name_lines"]) * line_h
        left_sy = summary_start
        right_sy = summary_start

        for line in row["left_summary_lines"]:
            if 0 <= left_sy < clip_h:
                s = self._font.render(line, True, left_colour)
                clip.blit(s, (left_x, left_sy))
            left_sy += line_h

        for line in row["right_summary_lines"]:
            if 0 <= right_sy < clip_h:
                s = self._font.render(line, True, right_colour)
                clip.blit(s, (right_x, right_sy))
            right_sy += line_h

        meta_y = max(left_sy, right_sy) + 2
        for line in row["left_meta_lines"]:
            if 0 <= meta_y < clip_h:
                s = self._label_font.render(line, True, _CLR_DIM)
                clip.blit(s, (left_x, meta_y))
            meta_y += lbl_h

        # Row separator line
        sep_y = draw_y + h - 2
        if 0 <= sep_y < clip_h:
            pygame.draw.line(clip, _CLR_DIVIDER, (0, sep_y), (clip.get_width(), sep_y))
