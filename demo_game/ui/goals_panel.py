"""
Module: goals_panel
Layer: demo_game.ui
Purpose: GOALS right-panel tab — shows the active NPC's Goal nodes with
         description, urgency progress bar, and status badge.
         Data pushed from NpcGoalsPoller via RightPanelRenderer.set_goals().
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
_CLR_STATUS_ACTIVE = PALETTE["green"]
_CLR_STATUS_COMPLETED = _CLR_GREY
_CLR_STATUS_FAILED = PALETTE["red"]

_PAD_X = 12
_PAD_Y = 12
_GOAL_BLOCK_H = 50     # height per goal block (urgency bar + description)
_BAR_H = 10
_MAX_DESC_CHARS = 52   # truncate long descriptions to fit the panel width
_URGENCY_MAX = 100

_SECTION_HDR = "GOALS"


def _status_colour(status: str | None) -> tuple[int, int, int]:
    """Return badge colour for a goal status string."""
    if not status or status in ("active", "in_progress", "pending"):
        return _CLR_STATUS_ACTIVE
    if status in ("completed", "done"):
        return _CLR_STATUS_COMPLETED
    return _CLR_STATUS_FAILED


def _urgency_colour(urgency: int) -> tuple[int, int, int]:
    """Return bar colour based on urgency (0=none, 100=critical)."""
    if urgency >= 75:
        return _CLR_RED
    if urgency >= 50:
        return _CLR_AMBER
    return _CLR_GREEN


class GoalsPanelWidget:
    """List of NPC Goal nodes with urgency bar and description.

    Call ``set_goals()`` after each NpcGoalsPoller tick. Goals are sorted
    descending by urgency so the most pressing goals appear first.

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
        self._goals: list[dict] = []

    # ------------------------------------------------------------------
    # Data setter
    # ------------------------------------------------------------------

    def set_goals(self, goals: list[dict]) -> None:
        """Replace the displayed goals list.

        Args:
            goals: List of Goal node dicts with at minimum
                   ``description``, ``urgency``, and ``status`` keys.
        """
        self._goals = sorted(goals, key=lambda g: -int(g.get("urgency", 0)))

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the goals panel inside rect.

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

        if not self._goals:
            _draw_centered(surface, self._font_label, "No goals data", _CLR_NO_DATA, rect)
            return

        bar_total_w = rect.width - 2 * _PAD_X
        for goal in self._goals:
            if y + _GOAL_BLOCK_H > rect.bottom:
                break
            y = self._draw_goal_block(surface, x, y, bar_total_w, goal)
            pygame.draw.line(
                surface, _CLR_BORDER,
                (rect.x + _PAD_X, y - 2), (rect.right - _PAD_X, y - 2),
            )

    def _draw_goal_block(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        total_w: int,
        goal: dict,
    ) -> int:
        """Draw one goal block; return y below the block."""
        urgency = int(goal.get("urgency", 0))
        description = str(goal.get("description", ""))
        status = str(goal.get("status", "active"))

        bar_clr = _urgency_colour(urgency)
        status_clr = _status_colour(status)

        # Row 1: urgency label + bar + status badge
        urg_lbl = self._font_label.render(f"urgency {urgency}", True, _CLR_MUTED)
        surface.blit(urg_lbl, (x, y))

        status_surf = self._font_label.render(status, True, status_clr)
        status_x = x + total_w - status_surf.get_width()
        surface.blit(status_surf, (status_x, y))

        bar_x = x + urg_lbl.get_width() + 6
        bar_w = status_x - bar_x - 6
        bar_rect = pygame.Rect(bar_x, y + 3, max(bar_w, 0), _BAR_H)
        pygame.draw.rect(surface, _CLR_BAR_BG, bar_rect, border_radius=3)

        ratio = max(0.0, min(1.0, urgency / _URGENCY_MAX))
        filled_w = int(bar_w * ratio)
        if filled_w > 0:
            pygame.draw.rect(
                surface, bar_clr,
                pygame.Rect(bar_x, y + 3, filled_w, _BAR_H),
                border_radius=3,
            )
        y += _BAR_H + 8

        # Row 2: description (truncated)
        truncated = description[:_MAX_DESC_CHARS] + ("…" if len(description) > _MAX_DESC_CHARS else "")
        desc_surf = self._font_label.render(truncated, True, _CLR_WHITE)
        surface.blit(desc_surf, (x, y))
        y += desc_surf.get_height() + 10

        return y


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
