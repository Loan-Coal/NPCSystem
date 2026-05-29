"""
Module: left_panel
Layer: demo_game.ui
Purpose: Left panel renderer — location bar, world-state bar, NPC list, dialogue log,
         degradation badge, action bar, and input box.
Dependencies: pygame, demo_game.constants, demo_game.ui.widgets, demo_game.ui.action_bar
Used by: demo_game.ui.game_window

300-line exception: single-class renderer with one concern (left panel). Splitting would
scatter rendering logic across files with no encapsulation gain. See DEC-036.
"""

from __future__ import annotations

import time

import pygame

from demo_game.constants import (
    FACTION_COLOURS,
    LOCATION_DISPLAY_NAMES,
    LOCATION_NPC_MAP,
    LOCATION_TINTS,
    NPC_DISPLAY_NAMES,
    NPC_FACTIONS,
    PALETTE,
)
from demo_game.ui.action_bar import ActionBarWidget
from demo_game.ui.widgets import DegradationBadge, EventBanner, InputBox, NpcListWidget, ScrollableLog

# Fixed UI element heights — do not scale with window size.
_LOC_BAR_H = 80
_NPC_LIST_ROW_H = 36
_PORTRAIT_ZONE_H = 96
_NPC_HEADER_H = 24
_WORLD_STATE_BAR_H = 20
_BADGE_H = 28
_ACTION_BAR_H = 32
_INPUT_H = 40

_CLR_NPC_HEADER_BG   = PALETTE["bg"]
_CLR_NPC_HEADER_TEXT = PALETTE["amber"]
_CLR_NPC_HEADER_IDLE = PALETTE["grey"]


class LeftPanelRenderer:
    """Owns and renders all left-panel widgets.

    GameWindow creates this once and calls draw() each frame with current world-state
    data. State changes (active NPC, location, emotion) are applied via setters.

    Args:
        font_body: Monospace font for dialogue text (14px).
        font_label: Monospace font for labels and badges (12px).
        font_nav: Font for headers and status strips (14px).
        font_loc: Bold font for the location title (16px).
    """

    def __init__(
        self,
        font_body: pygame.font.Font,
        font_label: pygame.font.Font,
        font_nav: pygame.font.Font,
        font_loc: pygame.font.Font,
    ) -> None:
        self._font_body = font_body
        self._font_label = font_label
        self._font_nav = font_nav
        self._font_loc = font_loc

        self._input = InputBox(font_body)
        self._logs: dict[str, ScrollableLog] = {}
        self._npc_list = NpcListWidget(font_body, row_height=_NPC_LIST_ROW_H)
        self._badge = DegradationBadge(font_label)

        self._action_bar = ActionBarWidget(font_label)
        self._trade_price: int | None = None       # fair price from get_item_price
        self._trade_price_until: float = 0.0
        self._trade_state: str = "idle"            # "idle" | "offered_low" | "accepted"
        self._trade_result: dict | None = None     # last post_trade response
        self._trade_offered: int | None = None
        self._trade_fair: int | None = None
        self._trade_result_until: float = 0.0
        self._event_banner = EventBanner(font_label)

        self._active_npc_id: str = ""
        self._active_location_id: str = ""
        self._gradient_cache: dict[str, pygame.Surface] = {}
        # None sentinel means "tried loading PNG, failed — use geometric fallback".
        self._portrait_cache: dict[str, pygame.Surface | None] = {}

    # ------------------------------------------------------------------
    # State setters — called by GameWindow each frame or on events
    # ------------------------------------------------------------------

    def setup(self, location_id: str, npc_id: str) -> None:
        """Set the initial location and active NPC at startup."""
        self._active_location_id = location_id
        self._active_npc_id = npc_id
        self._npc_list.set_npcs(LOCATION_NPC_MAP[location_id], NPC_DISPLAY_NAMES, npc_id)

    def set_location(self, location_id: str, active_npc_id: str) -> None:
        """Switch to a new location and update the NPC list."""
        self._active_location_id = location_id
        self._active_npc_id = active_npc_id
        self._npc_list.set_npcs(LOCATION_NPC_MAP[location_id], NPC_DISPLAY_NAMES, active_npc_id)

    def set_active_npc(self, npc_id: str) -> None:
        """Update the active NPC without changing the NPC list."""
        self._active_npc_id = npc_id

    def set_emotion(self, label: str, valence: float) -> None:
        """Forward emotion update from EmotionPoller to the badge."""
        self._badge.set_emotion(label, valence)

    def set_waiting(self, waiting: bool) -> None:
        """Disable the input box while a dialogue reply is in-flight."""
        self._input.disabled = waiting

    def add_player_message(self, npc_id: str, text: str) -> None:
        """Append a player-turn line to the given NPC's dialogue log."""
        self.get_log(npc_id).add_message("You", text, is_player=True)

    def add_npc_response(
        self,
        npc_id: str,
        text: str,
        degradation_level: int,
        emotion: str,
        color: tuple,
    ) -> None:
        """Append an NPC-turn line and update the degradation badge."""
        speaker = NPC_DISPLAY_NAMES.get(npc_id, npc_id)
        self.get_log(npc_id).add_message(speaker, text)
        self._badge.set(degradation_level, emotion, color)

    def add_error(self, npc_id: str, text: str) -> None:
        """Append an error line to the given NPC's dialogue log."""
        self.get_log(npc_id).add_message("ERROR", text, is_error=True)

    def get_log(self, npc_id: str) -> ScrollableLog:
        """Return the ScrollableLog for npc_id, creating it lazily on first use."""
        if npc_id not in self._logs:
            self._logs[npc_id] = ScrollableLog(self._font_body, self._font_label)
        return self._logs[npc_id]

    def handle_scroll(self, event: pygame.event.Event) -> None:
        """Route MOUSEWHEEL events to the active NPC's dialogue log."""
        if self._active_npc_id:
            self.get_log(self._active_npc_id).handle_event(event)

    def handle_action_bar(self, event: pygame.event.Event) -> str | None:
        """Route a click to the action bar. Return preset text if a button was hit."""
        return self._action_bar.handle_event(event)

    def set_trade_price(self, price: int | None, duration_s: float = 4.0) -> None:
        """Display a trade price overlay for duration_s seconds."""
        self._trade_price = price
        self._trade_price_until = time.monotonic() + duration_s

    def show_event_banner(self, label: str, duration_s: float = 2.0) -> None:
        """Flash the event banner with label for duration_s seconds."""
        self._event_banner.show(label, duration_s)

    def get_trade_state(self) -> str:
        """Return current trade state: ``'idle'``, ``'offered_low'``, or ``'accepted'``."""
        return self._trade_state

    def apply_trade_result(
        self,
        result: dict,
        offered: int,
        fair: int,
        duration_s: float = 8.0,
    ) -> None:
        """Advance the trade state machine and store the result for overlay rendering.

        Transitions ``idle → offered_low → accepted``. Accepted is terminal.

        Args:
            result: Full API response from ``post_trade()``.
            offered: Price that was offered this click.
            fair: The fair market price (from ``get_item_price``).
            duration_s: How long the result overlay stays visible.
        """
        if self._trade_state == "idle":
            self._trade_state = "offered_low"
        elif self._trade_state == "offered_low":
            self._trade_state = "accepted"
        self._trade_result = result
        self._trade_offered = offered
        self._trade_fair = fair
        self._trade_result_until = time.monotonic() + duration_s

    def reset_trade_state(self) -> None:
        """Reset the trade state machine — call when the active NPC changes."""
        self._trade_state = "idle"
        self._trade_result = None
        self._trade_offered = None
        self._trade_fair = None
        self._trade_result_until = 0.0
        self._trade_price = None
        self._trade_price_until = 0.0

    # ------------------------------------------------------------------
    # Widget accessors — for GameWindow event routing
    # ------------------------------------------------------------------

    @property
    def input(self) -> InputBox:
        """The text input box widget."""
        return self._input

    @property
    def npc_list(self) -> NpcListWidget:
        """The NPC list widget."""
        return self._npc_list

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(
        self,
        screen: pygame.Surface,
        left_w: int,
        usable_h: int,
        epoch: str | None,
        conditions: list[str],
    ) -> None:
        """Draw the complete left panel onto screen.

        Args:
            screen: Target surface.
            left_w: Pixel width of the left panel.
            usable_h: Available height (window height minus nav bar height).
            epoch: Current world-state epoch, or None if not yet polled.
            conditions: List of active world condition IDs.
        """
        npc_count = len(LOCATION_NPC_MAP.get(self._active_location_id, []))
        npc_list_h = npc_count * _NPC_LIST_ROW_H

        self._draw_location_bar(screen, pygame.Rect(0, 0, left_w, _LOC_BAR_H))
        self._draw_world_state_bar(
            screen,
            pygame.Rect(0, _LOC_BAR_H, left_w, _WORLD_STATE_BAR_H),
            epoch,
            conditions,
        )

        npc_list_y = _LOC_BAR_H + _WORLD_STATE_BAR_H
        self._npc_list.draw(screen, pygame.Rect(0, npc_list_y, left_w, npc_list_h))

        portrait_y = npc_list_y + npc_list_h + 4
        self._draw_portrait_zone(screen, pygame.Rect(0, portrait_y, left_w, _PORTRAIT_ZONE_H))

        header_y = portrait_y + _PORTRAIT_ZONE_H
        self._draw_npc_header(screen, pygame.Rect(0, header_y, left_w, _NPC_HEADER_H))

        badge_y = usable_h - _BADGE_H - _ACTION_BAR_H - _INPUT_H - 10
        log_y = header_y + _NPC_HEADER_H + 2
        log_h = badge_y - log_y - 4
        if self._active_npc_id and log_h > 0:
            self.get_log(self._active_npc_id).draw(
                screen, pygame.Rect(0, log_y, left_w, log_h)
            )
            self._draw_trade_overlay(screen, pygame.Rect(0, log_y, left_w, log_h))

        self._badge.draw(screen, pygame.Rect(0, badge_y, left_w, _BADGE_H))
        action_y = badge_y + _BADGE_H + 2
        self._action_bar.draw(screen, pygame.Rect(0, action_y, left_w, _ACTION_BAR_H))
        self._input.draw(screen, pygame.Rect(0, action_y + _ACTION_BAR_H + 2, left_w, _INPUT_H))
        self._event_banner.draw(screen, pygame.Rect(0, 0, left_w, usable_h))

    def _draw_trade_overlay(self, screen: pygame.Surface, log_rect: pygame.Rect) -> None:
        now = time.monotonic()
        if self._trade_result is not None and now < self._trade_result_until:
            data = self._trade_result.get("data", self._trade_result)
            accepted = bool(data.get("accepted", False))
            reason = str(data.get("rejection_reason") or "")
            result_line = "ACCEPTED" if accepted else f"REJECTED — {reason!r}" if reason else "REJECTED"
            lines = [
                "Item: northern spice bundle",
                f"Offered: {self._trade_offered} gold  |  Fair: {self._trade_fair} gold",
                f"Result: {result_line}",
            ]
            lh = self._font_label.get_linesize()
            olh = lh * len(lines) + 10
            olr = pygame.Rect(log_rect.x, log_rect.bottom - olh, log_rect.width, olh)
            pygame.draw.rect(screen, PALETTE["panel"], olr)
            pygame.draw.rect(screen, PALETTE["border"], olr, 1)
            for i, line in enumerate(lines):
                colour = PALETTE["green"] if (i == 2 and accepted) else (
                    PALETTE["red"] if (i == 2 and not accepted) else PALETTE["white"]
                )
                screen.blit(
                    self._font_label.render(line, True, colour),
                    (olr.x + 6, olr.y + 5 + i * lh),
                )
        elif self._trade_price is not None and now < self._trade_price_until:
            lh = self._font_label.get_linesize()
            olh = lh + 8
            olr = pygame.Rect(log_rect.x, log_rect.bottom - olh, log_rect.width, olh)
            pygame.draw.rect(screen, PALETTE["bg"], olr)
            screen.blit(
                self._font_label.render(
                    f"Aldric: northern spice — {self._trade_price} gold",
                    True, PALETTE["amber"],
                ),
                (olr.x + 8, olr.y + 4),
            )

    def _draw_location_bar(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        cache_key = f"{self._active_location_id}:{rect.width}"
        if cache_key not in self._gradient_cache:
            self._gradient_cache[cache_key] = self._build_gradient(
                LOCATION_TINTS.get(self._active_location_id, PALETTE["bg"]),
                rect.width,
                rect.height,
            )
        screen.blit(self._gradient_cache[cache_key], (rect.x, rect.y))
        name = LOCATION_DISPLAY_NAMES.get(self._active_location_id, self._active_location_id)
        txt = self._font_loc.render(name, True, PALETTE["white"])
        screen.blit(txt, (rect.x + 12, rect.centery - txt.get_height() // 2))

    @staticmethod
    def _build_gradient(
        tint: tuple[int, int, int],
        width: int,
        height: int,
    ) -> pygame.Surface:
        """Build a vertical gradient surface blending tint (top) to PALETTE["bg"] (bottom)."""
        bg = PALETTE["bg"]
        surf = pygame.Surface((width, height))
        for y in range(height):
            t = y / max(height - 1, 1)
            r = int(tint[0] * (1 - t) + bg[0] * t)
            g = int(tint[1] * (1 - t) + bg[1] * t)
            b = int(tint[2] * (1 - t) + bg[2] * t)
            pygame.draw.line(surf, (r, g, b), (0, y), (width, y))
        return surf

    def _draw_world_state_bar(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        epoch: str | None,
        conditions: list[str],
    ) -> None:
        """Draw a thin strip showing the current epoch and active conditions."""
        pygame.draw.rect(screen, _CLR_NPC_HEADER_BG, rect)
        clr = _CLR_NPC_HEADER_TEXT if (epoch and epoch != "peace") else _CLR_NPC_HEADER_IDLE
        cond_str = ", ".join(conditions) if conditions else "—"
        label = f"Epoch: {epoch or '—'}  |  {cond_str}"
        txt = self._font_label.render(label, True, clr)
        screen.blit(txt, (rect.x + 10, rect.centery - txt.get_height() // 2))

    def _draw_npc_header(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw the 'Talking to [NPC name]' strip above the dialogue log."""
        pygame.draw.rect(screen, _CLR_NPC_HEADER_BG, rect)
        npc_id = self._active_npc_id
        if npc_id:
            name = NPC_DISPLAY_NAMES.get(npc_id, npc_id)
            label = f"Talking to  {name}"
            clr = _CLR_NPC_HEADER_TEXT
        else:
            label = "Select an NPC to begin"
            clr = _CLR_NPC_HEADER_IDLE
        txt = self._font_nav.render(label, True, clr)
        screen.blit(txt, (rect.x + 10, rect.centery - txt.get_height() // 2))

    def _draw_portrait_zone(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw the active NPC's portrait (PNG or geometric fallback) in rect."""
        pygame.draw.rect(surface, PALETTE["bg"], rect)
        npc_id = self._active_npc_id
        if not npc_id:
            return
        if npc_id not in self._portrait_cache:
            try:
                img = pygame.image.load(f"demo_game/assets/portraits/{npc_id}.png")
                self._portrait_cache[npc_id] = pygame.transform.scale(img, (80, 80))
            except Exception:
                self._portrait_cache[npc_id] = None
        cached = self._portrait_cache[npc_id]
        if cached is not None:
            surface.blit(cached, (rect.centerx - 40, rect.centery - 40))
        else:
            self._draw_portrait_geometric(surface, rect, npc_id)

    def _draw_portrait_geometric(
        self, surface: pygame.Surface, rect: pygame.Rect, npc_id: str
    ) -> None:
        """Draw a faction-coloured circle with the NPC's first initial."""
        faction = NPC_FACTIONS.get(npc_id, "neutral")
        colour = FACTION_COLOURS.get(faction, PALETTE["grey"])
        centre = (rect.centerx, rect.centery)
        pygame.draw.circle(surface, colour, centre, 38)
        name = NPC_DISPLAY_NAMES.get(npc_id, npc_id)
        initial = name[0].upper() if name else "?"
        txt = self._font_loc.render(initial, True, PALETTE["white"])
        surface.blit(txt, (centre[0] - txt.get_width() // 2, centre[1] - txt.get_height() // 2))
