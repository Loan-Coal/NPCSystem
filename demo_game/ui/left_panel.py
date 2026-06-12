"""
Module: left_panel
Layer: demo_game.ui
Purpose: Left panel renderer — location bar, world-state bar, NPC list, dialogue log,
         degradation badge, action bar, and input box. Includes PART_OF breadcrumb
         helpers (EXP-221) rendered below the location title.
Dependencies: pygame, demo_game.constants, demo_game.ui.widgets, demo_game.ui.action_bar
Used by: demo_game.ui.game_window

300-line exception: single-class renderer with one concern (left panel). Splitting would
scatter rendering logic across files with no encapsulation gain. See DEC-036.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

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

# Maps NPC facial_expression strings to display glyphs.
# Unknown or None expressions fall back to the "neutral" entry — no crash.
EXPRESSION_GLYPHS: dict[str, str] = {
    "neutral":   "😐",
    "happy":     "😊",
    "sad":       "😢",
    "angry":     "😠",
    "fearful":   "😨",
    "surprised": "😲",
    "disgusted": "🤢",
    "confused":  "😕",
    "smug":      "😏",
    "worried":   "😟",
}

_NEUTRAL_GLYPH: str = EXPRESSION_GLYPHS["neutral"]

# Separator rendered between breadcrumb segments.
_BREADCRUMB_SEP: str = " ▸ "

# Guard against malformed PART_OF cycles in the graph.
_BREADCRUMB_MAX_DEPTH: int = 10


def build_location_breadcrumb(
    location_id: str,
    get_edges: Callable[..., list[dict]],
) -> str:
    """Walk PART_OF edges upward from location_id and return a breadcrumb string.

    Queries PART_OF edges using the provided callable (mirrors
    ``EngineClient.get_graph_edges``). Degrades gracefully when no parent exists —
    returns the bare location_id. A cycle guard caps traversal at
    ``_BREADCRUMB_MAX_DEPTH`` hops to prevent infinite loops on malformed graphs.

    Args:
        location_id: Starting Location node ID.
        get_edges: Callable matching ``client.get_graph_edges(edge_type, src_id=...)``
                   signature — returns a list of edge dicts each with a ``dst_id`` key.

    Returns:
        Breadcrumb string, e.g. ``"tavern ▸ market_district ▸ kingsport"``, or just
        ``"tavern"`` when no PART_OF parent exists.
    """
    segments: list[str] = [location_id]
    visited: set[str] = {location_id}
    current = location_id

    for _ in range(_BREADCRUMB_MAX_DEPTH):
        edges = get_edges("PART_OF", src_id=current)
        if not edges:
            break
        parent_id: str = edges[0].get("dst_id", "")
        if not parent_id or parent_id in visited:
            break
        segments.append(parent_id)
        visited.add(parent_id)
        current = parent_id

    return _BREADCRUMB_SEP.join(segments)


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
        self._event_banner = EventBanner(font_label)

        self._active_npc_id: str = ""
        self._active_location_id: str = ""
        self._player_gold: int | None = None
        self._facial_expression: str | None = None
        self._relationship_phase: str | None = None
        self._gradient_cache: dict[str, pygame.Surface] = {}
        # None sentinel means "tried loading PNG, failed — use geometric fallback".
        self._portrait_cache: dict[str, pygame.Surface | None] = {}
        # Optional callable matching client.get_graph_edges(edge_type, src_id=…).
        # Set by game_window once so the location bar can render breadcrumbs.
        self._get_graph_edges: object | None = None

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

    def set_player_gold(self, gold: int | None) -> None:
        """Update the displayed player gold balance in the world-state bar."""
        self._player_gold = gold

    def set_facial_expression(self, expression: str | None) -> None:
        """Store the NPC's current facial expression for glyph rendering.

        Args:
            expression: Expression key matching EXPRESSION_GLYPHS (e.g. ``"angry"``),
                or None. Unknown/None values fall back to the neutral glyph — no crash.
        """
        self._facial_expression = expression

    def set_relationship_phase(self, phase: str | None) -> None:
        """Store the NPC's current relationship phase for rendering in the portrait zone.

        Args:
            phase: Phase string (e.g. ``"acquaintance"``, ``"ally"``), or None.
                When None or absent the phase line is simply not drawn — no crash.
        """
        self._relationship_phase = phase

    def set_graph_edges_fn(self, fn: object) -> None:
        """Store the callable used to fetch PART_OF edges for breadcrumb rendering.

        Args:
            fn: Callable matching ``client.get_graph_edges(edge_type, src_id=…)``.
                Stored as-is; called lazily inside ``_draw_location_bar``.
        """
        self._get_graph_edges = fn

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

    def begin_streaming_npc_response(self, npc_id: str) -> None:
        """Open a new empty streaming entry in the NPC's dialogue log.

        Must be called once before the first ``append_npc_token`` for a response.
        The entry is rendered as it fills in — the log rerenders each frame.

        Args:
            npc_id: NPC whose log receives the streaming entry.
        """
        speaker = NPC_DISPLAY_NAMES.get(npc_id, npc_id)
        self.get_log(npc_id).begin_streaming(speaker)

    def append_npc_token(self, npc_id: str, token: str) -> None:
        """Append one streamed token to the active NPC log entry.

        Args:
            npc_id: NPC whose log entry receives the token.
            token: Word chunk (with optional trailing whitespace).
        """
        self.get_log(npc_id).append_stream_token(token)

    def update_badge(self, degradation_level: str, emotion: str | None, color: tuple) -> None:
        """Update the degradation badge after streaming completes.

        Called by GameController when the WS ``done`` message arrives, after
        all tokens have been streamed into the log.

        Args:
            degradation_level: Engine degradation tier (``"full"`` / ``"graph_only"`` / ``"canned"``).
            emotion: Emotion label from the response, or None.
            color: RGB badge background colour matching the degradation tier.
        """
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

    def show_event_banner(self, label: str, duration_s: float = 2.0) -> None:
        """Flash the event banner with label for duration_s seconds."""
        self._event_banner.show(label, duration_s)

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
        self._badge.draw(screen, pygame.Rect(0, badge_y, left_w, _BADGE_H))
        action_y = badge_y + _BADGE_H + 2
        self._action_bar.draw(screen, pygame.Rect(0, action_y, left_w, _ACTION_BAR_H))
        self._input.draw(screen, pygame.Rect(0, action_y + _ACTION_BAR_H + 2, left_w, _INPUT_H))
        self._event_banner.draw(screen, pygame.Rect(0, 0, left_w, usable_h))

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
        if self._get_graph_edges is not None:
            try:
                breadcrumb = build_location_breadcrumb(
                    self._active_location_id, self._get_graph_edges  # type: ignore[arg-type]
                )
                self._draw_location_breadcrumb(screen, rect, breadcrumb)
            except Exception:
                pass  # breadcrumb is cosmetic — never crash the render loop

    def _draw_location_breadcrumb(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        breadcrumb: str,
    ) -> None:
        """Render the PART_OF breadcrumb string in the lower portion of the location bar.

        Draws a small label below the location title using ``_font_label``.
        When the breadcrumb is just the bare location name (no parents) the call
        is a no-op — the location title already shows the name.

        Args:
            screen: Target surface.
            rect: Bounding rect for the location bar area.
            breadcrumb: Pre-built breadcrumb string from ``build_location_breadcrumb``.
        """
        if _BREADCRUMB_SEP not in breadcrumb:
            return
        txt = self._font_label.render(breadcrumb, True, PALETTE.get("grey", (150, 150, 150)))
        y = rect.bottom - txt.get_height() - 4
        screen.blit(txt, (rect.x + 12, y))

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

    def _draw_relationship_phase(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the relationship phase label in the lower-left of the portrait zone.

        Shows nothing (no crash) when ``_relationship_phase`` is None.

        Args:
            surface: Target surface (the portrait zone's parent surface).
            rect: Bounding rect of the portrait zone.
        """
        if not self._relationship_phase:
            return
        label = f"Phase: {self._relationship_phase}"
        txt = self._font_label.render(label, True, PALETTE.get("grey", (150, 150, 150)))
        screen_x = rect.x + 4
        screen_y = rect.bottom - txt.get_height() - 4
        surface.blit(txt, (screen_x, screen_y))

    def _draw_world_state_bar(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        epoch: str | None,
        conditions: list[str],
    ) -> None:
        """Draw a thin strip showing the current epoch, active conditions, and player gold."""
        pygame.draw.rect(screen, _CLR_NPC_HEADER_BG, rect)
        clr = _CLR_NPC_HEADER_TEXT if (epoch and epoch != "peace") else _CLR_NPC_HEADER_IDLE
        cond_str = ", ".join(conditions) if conditions else "—"
        label = f"Epoch: {epoch or '—'}  |  {cond_str}"
        txt = self._font_label.render(label, True, clr)
        screen.blit(txt, (rect.x + 10, rect.centery - txt.get_height() // 2))
        if self._player_gold is not None:
            gold_label = f"Gold: {self._player_gold}"
            gold_surf = self._font_label.render(gold_label, True, PALETTE["amber"])
            gold_x = rect.right - gold_surf.get_width() - 10
            screen.blit(gold_surf, (gold_x, rect.centery - gold_surf.get_height() // 2))

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
        """Draw the active NPC's portrait (PNG or geometric fallback) plus expression glyph."""
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
        self._draw_expression_glyph(surface, rect)
        self._draw_relationship_phase(surface, rect)

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

    def _draw_expression_glyph(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the expression glyph in the lower-right corner of the portrait zone.

        Resolves the stored facial_expression via EXPRESSION_GLYPHS; unknown or None
        values fall back to the neutral glyph so the UI never crashes.

        Args:
            surface: Target surface (the portrait zone's parent surface).
            rect: Bounding rect of the portrait zone.
        """
        glyph = EXPRESSION_GLYPHS.get(self._facial_expression or "", _NEUTRAL_GLYPH)
        txt = self._font_loc.render(glyph, True, PALETTE["white"])
        x = rect.right - txt.get_width() - 4
        y = rect.bottom - txt.get_height() - 4
        surface.blit(txt, (x, y))
