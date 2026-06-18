"""
Module: world_panel
Layer: demo_game.ui
Purpose: WORLD right-panel tab — three sections: OBJECTIVE progress (top),
         engine-status table (middle), and live event feed (bottom, scrollable).
Does NOT: make HTTP calls or hold mutable engine state.
Dependencies: pygame, demo_game.constants, demo_game.game_end_checker
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from demo_game.constants import DEMO_FACTIONS, PALETTE, WIN_STANDING_THRESHOLD

if TYPE_CHECKING:
    from demo_game.game_end_checker import ObjectiveState

# Colours
_CLR_BG = PALETTE["bg"]
_CLR_PANEL = PALETTE["panel"]
_CLR_BORDER = PALETTE["border"]
_CLR_AMBER = PALETTE["amber"]
_CLR_WHITE = PALETTE["white"]
_CLR_GREY = PALETTE["grey"]
_CLR_GREEN = PALETTE["green"]
_CLR_RED = PALETTE["red"]

# Section geometry
_SECTION_HDR_H = 20     # "OBJECTIVE" / "ENGINES" / "EVENTS" section header height
_OBJECTIVE_ROW_H = 18   # height of one faction standing row
_FACTION_BAR_W = 80     # width of the faction standing bar
_FACTION_BAR_H = 10     # height of the faction standing bar
_ENGINE_ROW_H = 18      # height of one engine status row
_ENGINE_TABLE_MAX_ROWS = 8
_EVENT_ROW_H = 16       # height of one event row
_PAD_X = 6
_PAD_Y = 4
_DIVIDER_H = 2

# Faction display names for the objective bar.
_FACTION_DISPLAY: dict[str, str] = {
    "merchants_guild": "Merchants",
    "city_guard":      "City Guard",
    "thieves_guild":   "Thieves",
}

# Outcome banner colours.
_CLR_WIN_BG = (20, 80, 30)
_CLR_WIN_TEXT = (60, 220, 80)
_CLR_LOSE_BG = (80, 15, 15)
_CLR_LOSE_TEXT = (220, 60, 60)
_CLR_THREAT = (180, 80, 40)

# Status badge colours
_STATUS_OK = _CLR_GREEN
_STATUS_ERROR = _CLR_RED
_STATUS_IDLE = _CLR_GREY


def _engine_badge_color(record: dict) -> tuple[int, int, int]:
    """Return badge colour for an engine status record."""
    if record.get("last_error") and record.get("last_error_tick") == record.get("last_tick_id"):
        return _STATUS_ERROR
    if record.get("last_tick_id") is None:
        return _STATUS_IDLE
    return _STATUS_OK


def _engine_status_label(record: dict) -> str:
    """Return a short status label for an engine."""
    if record.get("last_error") and record.get("last_error_tick") == record.get("last_tick_id"):
        return "ERR"
    if record.get("last_tick_id") is None:
        return "IDLE"
    return "OK"


class WorldPanelWidget:
    """Three-section WORLD panel: objective progress, engine-status, event feed.

    Push fresh data before each draw call via ``set_engines()`` / ``set_events()``
    / ``set_objective()``.

    Args:
        font_body: Main body font for row text.
        font_label: Smaller font for section headers and badges.
    """

    def __init__(
        self,
        font_body: pygame.font.Font,
        font_label: pygame.font.Font,
    ) -> None:
        self._font = font_body
        self._font_label = font_label
        self._engines: list[dict] = []
        self._events: list[dict] = []
        self._scroll_y: int = 0
        self._objective: ObjectiveState | None = None

    # ------------------------------------------------------------------
    # Data setters
    # ------------------------------------------------------------------

    def set_engines(self, engines: list[dict]) -> None:
        """Push a fresh engine-status list into the widget."""
        self._engines = engines

    def set_events(self, events: list[dict]) -> None:
        """Push a fresh event list into the widget (replaces previous snapshot)."""
        self._events = events

    def set_objective(self, objective: ObjectiveState) -> None:
        """Push a fresh ObjectiveState into the widget."""
        self._objective = objective

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle MOUSEWHEEL events to scroll the event feed."""
        if event.type == pygame.MOUSEWHEEL:
            total_h = len(self._events) * _EVENT_ROW_H
            self._scroll_y = max(0, min(self._scroll_y - event.y * 20, total_h))

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render objective, engine table, and event feed into rect.

        Args:
            surface: Target surface.
            rect: Content area (below the tab header strip).
        """
        pygame.draw.rect(surface, _CLR_BG, rect)
        y = rect.y + _PAD_Y
        y = self._draw_objective_section(surface, rect, y)
        y += _DIVIDER_H
        pygame.draw.line(surface, _CLR_BORDER, (rect.x + _PAD_X, y), (rect.right - _PAD_X, y))
        y += _DIVIDER_H + _PAD_Y
        y = self._draw_engines_section(surface, rect, y)
        y += _DIVIDER_H
        pygame.draw.line(surface, _CLR_BORDER, (rect.x + _PAD_X, y), (rect.right - _PAD_X, y))
        y += _DIVIDER_H + _PAD_Y
        self._draw_events_section(surface, rect, y)

    def _draw_objective_section(
        self, surface: pygame.Surface, rect: pygame.Rect, y: int
    ) -> int:
        """Draw the OBJECTIVE section; return the y position after the section."""
        obj = self._objective

        # Header with optional outcome badge.
        if obj and obj.outcome == "win":
            pygame.draw.rect(surface, _CLR_WIN_BG, (rect.x, y, rect.width, _SECTION_HDR_H))
            lbl = self._font_label.render("OBJECTIVE  ★ YOU WIN ★", True, _CLR_WIN_TEXT)
        elif obj and obj.outcome == "lose":
            pygame.draw.rect(surface, _CLR_LOSE_BG, (rect.x, y, rect.width, _SECTION_HDR_H))
            lbl = self._font_label.render("OBJECTIVE  ✗ DEFEAT", True, _CLR_LOSE_TEXT)
        else:
            lbl = self._font_label.render("OBJECTIVE", True, _CLR_AMBER)
        surface.blit(lbl, (rect.x + _PAD_X, y))
        y += _SECTION_HDR_H

        # Win objective line.
        goal_txt = self._font_label.render(
            f"Trust 2/3 factions (standing ≥ {WIN_STANDING_THRESHOLD})", True, _CLR_GREY
        )
        surface.blit(goal_txt, (rect.x + _PAD_X, y))
        y += _OBJECTIVE_ROW_H

        # Earn-gold hint — hidden once game ends so it doesn't clutter the outcome screen.
        if not (obj and obj.outcome):
            hint_txt = self._font_label.render(
                "Earn gold: Aldric quest / spice trade → Bribe faction NPCs",
                True,
                _CLR_GREY,
            )
            surface.blit(hint_txt, (rect.x + _PAD_X, y))
        y += _OBJECTIVE_ROW_H

        standings = obj.faction_standings if obj else {}
        for faction_id in DEMO_FACTIONS:
            y = self._draw_faction_bar(surface, rect, y, faction_id, standings.get(faction_id, 0))

        # Lose threat line.
        if obj and obj.iron_legion_controls:
            threat_lbl = self._font_label.render(
                "Iron Legion controls: " + ", ".join(obj.iron_legion_controls),
                True,
                _CLR_THREAT,
            )
        else:
            threat_lbl = self._font_label.render("Iron Legion: no territories", True, _CLR_GREY)
        surface.blit(threat_lbl, (rect.x + _PAD_X, y))
        y += _OBJECTIVE_ROW_H

        return y

    def _draw_faction_bar(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        y: int,
        faction_id: str,
        standing: int,
    ) -> int:
        """Draw a faction standing bar row; return y after the row."""
        name = _FACTION_DISPLAY.get(faction_id, faction_id)
        met = standing >= WIN_STANDING_THRESHOLD
        name_color = _CLR_GREEN if met else _CLR_WHITE

        name_surf = self._font_label.render(f"{name}:", True, name_color)
        surface.blit(name_surf, (rect.x + _PAD_X, y + 2))

        # Clamped fill bar.
        bar_x = rect.x + _PAD_X + 70
        bar_y = y + (_OBJECTIVE_ROW_H - _FACTION_BAR_H) // 2
        pygame.draw.rect(surface, _CLR_BORDER, (bar_x, bar_y, _FACTION_BAR_W, _FACTION_BAR_H))
        fill_w = int(_FACTION_BAR_W * min(standing, 100) / 100)
        bar_color = _CLR_GREEN if met else _CLR_AMBER
        if fill_w > 0:
            pygame.draw.rect(surface, bar_color, (bar_x, bar_y, fill_w, _FACTION_BAR_H))

        val_surf = self._font_label.render(str(standing), True, name_color)
        surface.blit(val_surf, (bar_x + _FACTION_BAR_W + 4, y + 2))

        return y + _OBJECTIVE_ROW_H

    def _draw_engines_section(
        self, surface: pygame.Surface, rect: pygame.Rect, y: int
    ) -> int:
        """Draw the engine-status table; return the y position after the section."""
        lbl = self._font_label.render("ENGINES", True, _CLR_AMBER)
        surface.blit(lbl, (rect.x + _PAD_X, y))
        y += _SECTION_HDR_H

        if not self._engines:
            msg = self._font_label.render("No engine data yet…", True, _CLR_GREY)
            surface.blit(msg, (rect.x + _PAD_X, y))
            return y + _ENGINE_ROW_H

        for record in self._engines[:_ENGINE_TABLE_MAX_ROWS]:
            y = self._draw_engine_row(surface, rect, y, record)
        return y

    def _draw_engine_row(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        y: int,
        record: dict,
    ) -> int:
        """Draw one engine row; return y after the row."""
        badge_color = _engine_badge_color(record)
        status_lbl = _engine_status_label(record)
        tick_str = str(record.get("last_tick_id") or "—")
        name_str = record.get("engine_name", "?")
        errors = record.get("error_count", 0)

        # Badge
        badge_surf = self._font_label.render(f"[{status_lbl}]", True, badge_color)
        surface.blit(badge_surf, (rect.x + _PAD_X, y))

        # Engine name
        name_surf = self._font_label.render(name_str, True, _CLR_WHITE)
        surface.blit(name_surf, (rect.x + _PAD_X + 44, y))

        # Last tick
        tick_surf = self._font_label.render(f"t{tick_str}", True, _CLR_GREY)
        surface.blit(tick_surf, (rect.right - 80, y))

        # Error count badge if non-zero
        if errors:
            err_surf = self._font_label.render(f"{errors}err", True, _CLR_RED)
            surface.blit(err_surf, (rect.right - 40, y))

        return y + _ENGINE_ROW_H

    def _draw_events_section(
        self, surface: pygame.Surface, rect: pygame.Rect, y_start: int
    ) -> None:
        """Draw the scrollable event feed below y_start."""
        lbl = self._font_label.render("EVENTS", True, _CLR_AMBER)
        surface.blit(lbl, (rect.x + _PAD_X, y_start))
        feed_top = y_start + _SECTION_HDR_H

        clip = pygame.Rect(rect.x, feed_top, rect.width, rect.bottom - feed_top)
        old_clip = surface.get_clip()
        surface.set_clip(clip)

        if not self._events:
            msg = self._font_label.render("No events yet — advance the clock.", True, _CLR_GREY)
            surface.blit(msg, (rect.x + _PAD_X, feed_top))
            surface.set_clip(old_clip)
            return

        y = feed_top - self._scroll_y
        for event in self._events:
            if y + _EVENT_ROW_H < feed_top:
                y += _EVENT_ROW_H
                continue
            if y > rect.bottom:
                break
            self._draw_event_row(surface, rect, y, event)
            y += _EVENT_ROW_H

        surface.set_clip(old_clip)

    def _draw_event_row(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        y: int,
        event: dict,
    ) -> None:
        """Draw one event row."""
        tick_id = event.get("tick_id")
        label = event.get("label") or event.get("event_type") or "?"
        loc = event.get("location_id") or ""
        severity = event.get("severity")

        tick_color = _CLR_GREY
        tick_surf = self._font_label.render(
            f"t{tick_id}" if tick_id is not None else "t?",
            True,
            tick_color,
        )
        surface.blit(tick_surf, (rect.x + _PAD_X, y))

        label_color = _CLR_RED if (severity is not None and severity >= 8) else _CLR_WHITE
        label_surf = self._font_label.render(label[:36], True, label_color)
        surface.blit(label_surf, (rect.x + _PAD_X + 36, y))

        if loc:
            loc_surf = self._font_label.render(loc[:16], True, _CLR_GREY)
            surface.blit(loc_surf, (rect.right - loc_surf.get_width() - _PAD_X, y))
