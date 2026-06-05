"""
Module: game_window
Layer: demo_game.ui
Purpose: Main Pygame game window — left dialogue panel, right live graph panel,
         bottom location nav. Non-blocking dialogue and graph polling via daemon threads.
Dependencies: pygame, demo_game.client, demo_game.config, demo_game.dialogue,
              demo_game.constants, demo_game.ui.widgets, demo_game.graph_panel.poller,
              demo_game.sandbox_loop
Used by: demo_game.__main__
"""

from __future__ import annotations

import queue
import threading
import time
from typing import TYPE_CHECKING

import pygame

from demo_game.client import EngineClient, EngineClientError
from demo_game.ui.relation_ticker import RelationTicker
from demo_game.graph_panel.poller import GraphPoller
from demo_game.config import DemoConfig
from demo_game.constants import (
    LOCATION_DISPLAY_NAMES,
    LOCATION_NPC_MAP,
    LOCATION_TINTS,
    LOCATIONS,
    NPC_DISPLAY_NAMES,
)
from demo_game.dialogue import build_dialogue_payload, degradation_color, parse_dialogue_response
from demo_game.ui.widgets import DegradationBadge, InputBox, NpcListWidget, ScrollableLog

if TYPE_CHECKING:
    from demo_game.sandbox_loop import SandboxLoop

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
WINDOW_W, WINDOW_H = 1280, 720
LEFT_PANEL_RATIO = 0.60
NAV_BAR_H = 48
LOC_BAR_H = 36
NPC_LIST_ROW_H = 36
BADGE_H = 28
INPUT_H = 40
FPS = 30

# Right panel dimensions — derived once here so GraphPoller and _render agree.
_RIGHT_X = int(WINDOW_W * LEFT_PANEL_RATIO) + 4
_RIGHT_W = WINDOW_W - _RIGHT_X
_RIGHT_H = WINDOW_H - NAV_BAR_H

_CLR_BG = (18, 18, 24)
_CLR_NAV_BG = (14, 14, 20)
_CLR_NAV_BTN = (38, 38, 52)
_CLR_NAV_BTN_ACTIVE = (70, 90, 155)
_CLR_NAV_TEXT = (200, 200, 210)
_CLR_RIGHT_PLACEHOLDER = (30, 30, 40)
_CLR_PLACEHOLDER_TEXT = (70, 70, 90)
_CLR_TIMESTAMP = (120, 120, 140)


def _dialogue_worker(client: EngineClient, payload: dict, result_q: queue.Queue) -> None:
    """Background thread: call post_dialogue and push result or exception."""
    try:
        result_q.put(client.post_dialogue(**payload))
    except Exception as exc:
        result_q.put(exc)


class GameWindow:
    """Main game window: dialogue panel + live graph panel + location nav.

    Args:
        client: Initialised EngineClient.
        cfg: Demo runtime configuration.
    """

    def __init__(
        self,
        client: EngineClient,
        cfg: DemoConfig,
        sandbox_loop: SandboxLoop | None = None,
    ) -> None:
        self._client = client
        self._cfg = cfg
        self._sandbox_loop = sandbox_loop
        self._response_q: queue.Queue = queue.Queue()
        self._is_waiting = False

        self._active_location_id: str = LOCATIONS[0]
        self._active_npc_id: str = LOCATION_NPC_MAP[LOCATIONS[0]][0]

        pygame.init()
        self._screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_caption("NPC Engine — Demo")

        font_body = pygame.font.SysFont("monospace", 14)
        font_label = pygame.font.SysFont("monospace", 12)
        font_nav = pygame.font.SysFont("sans", 14)
        font_loc = pygame.font.SysFont("sans", 16, bold=True)

        self._font_nav = font_nav
        self._font_loc = font_loc

        self._input = InputBox(font_body)
        self._log = ScrollableLog(font_body, font_label)
        self._npc_list = NpcListWidget(font_body, row_height=NPC_LIST_ROW_H)
        self._badge = DegradationBadge(font_label)

        self._npc_list.set_npcs(
            LOCATION_NPC_MAP[self._active_location_id],
            NPC_DISPLAY_NAMES,
            self._active_npc_id,
        )

        self._status_text: str = ""
        self._status_until: float = 0.0

        self._graph_poller = GraphPoller(client, cfg, _RIGHT_W, _RIGHT_H)
        self._graph_poller.start()

        self._relation_ticker: RelationTicker = RelationTicker(client)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the game loop. Blocks until the window is closed."""
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                self._handle_event(event)

            self._poll_response_queue()
            self._render()
            pygame.display.flip()
            clock.tick(FPS)

        pygame.quit()

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _handle_event(self, event: pygame.event.Event) -> None:
        submitted = self._input.handle_event(event)
        if submitted:
            self._submit_dialogue(submitted)

        self._log.handle_event(event)

        clicked_npc = self._npc_list.handle_event(event)
        if clicked_npc and clicked_npc != self._active_npc_id:
            self._relation_ticker.reset_baseline(self._active_npc_id)
            self._active_npc_id = clicked_npc

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_nav_click(event.pos)

        if event.type == pygame.KEYDOWN:
            self._handle_key(event.key)

    def _handle_nav_click(self, pos: tuple[int, int]) -> None:
        nav_y = WINDOW_H - NAV_BAR_H
        if pos[1] < nav_y:
            return
        btn_w = WINDOW_W // len(LOCATIONS)
        idx = pos[0] // btn_w
        if 0 <= idx < len(LOCATIONS):
            loc_id = LOCATIONS[idx]
            if loc_id != self._active_location_id:
                self._change_location(loc_id)

    # ------------------------------------------------------------------
    # Key bindings — W: war epoch, C: clock advance
    # ------------------------------------------------------------------

    def _handle_key(self, key: int) -> None:
        if key == pygame.K_w:
            try:
                self._client.put_world_state("war", ["northern_war"])
                self._set_status("War declared!")
            except EngineClientError as exc:
                self._set_status(f"W error: {exc}")
        elif key == pygame.K_c:
            try:
                self._client.advance_clock(delta_ticks=1)
                self._set_status("Clock advanced")
            except EngineClientError as exc:
                self._set_status(f"C error: {exc}")
        elif key == pygame.K_s and self._sandbox_loop is not None:
            if self._sandbox_loop.is_running:
                self._sandbox_loop.stop()
                self._set_status("Auto-tick OFF")
            else:
                self._sandbox_loop.start()
                self._set_status("Auto-tick ON")

    def _set_status(self, text: str, duration: float = 2.0) -> None:
        self._status_text = text
        self._status_until = time.monotonic() + duration

    # ------------------------------------------------------------------
    # Location navigation
    # ------------------------------------------------------------------

    def _change_location(self, loc_id: str) -> None:
        self._relation_ticker.reset_baseline(self._active_npc_id)
        self._active_location_id = loc_id
        npcs = LOCATION_NPC_MAP[loc_id]
        self._active_npc_id = npcs[0]
        self._npc_list.set_npcs(npcs, NPC_DISPLAY_NAMES, self._active_npc_id)

    # ------------------------------------------------------------------
    # Dialogue — submit + background worker
    # ------------------------------------------------------------------

    def _submit_dialogue(self, text: str) -> None:
        if self._is_waiting:
            return
        npc_id = self._npc_list.active_id or self._active_npc_id
        payload = build_dialogue_payload(
            npc_id,
            text,
            player_id=self._cfg.DEMO_PLAYER_ID,
            location_id=self._active_location_id,
        )
        self._log.add_message("You", text, is_player=True)
        self._input.disabled = True
        self._is_waiting = True
        threading.Thread(
            target=_dialogue_worker,
            args=(self._client, payload, self._response_q),
            daemon=True,
        ).start()

    def _poll_response_queue(self) -> None:
        try:
            item = self._response_q.get_nowait()
        except queue.Empty:
            return

        self._is_waiting = False
        self._input.disabled = False
        npc_id = self._npc_list.active_id or self._active_npc_id

        if isinstance(item, (Exception, EngineClientError)):
            self._log.add_message("ERROR", str(item), is_error=True)
            return

        turn = parse_dialogue_response(item)
        self._log.add_message(NPC_DISPLAY_NAMES.get(npc_id, npc_id), turn.npc_text)
        color = degradation_color(turn.degradation_level)
        self._badge.set(turn.degradation_level, turn.emotion, color)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> None:
        self._screen.fill(_CLR_BG)
        left_w = int(WINDOW_W * LEFT_PANEL_RATIO)
        right_x = left_w + 4
        right_w = WINDOW_W - right_x
        usable_h = WINDOW_H - NAV_BAR_H

        self._draw_location_bar(pygame.Rect(0, 0, left_w, LOC_BAR_H))

        npc_count = len(LOCATION_NPC_MAP[self._active_location_id])
        npc_list_h = npc_count * NPC_LIST_ROW_H
        self._npc_list.draw(self._screen, pygame.Rect(0, LOC_BAR_H, left_w, npc_list_h))

        badge_y = usable_h - BADGE_H - INPUT_H - 6
        log_y = LOC_BAR_H + npc_list_h + 4
        log_h = badge_y - log_y - 4
        self._log.draw(self._screen, pygame.Rect(0, log_y, left_w, log_h))

        self._badge.draw(self._screen, pygame.Rect(0, badge_y, left_w, BADGE_H))
        self._input.draw(self._screen, pygame.Rect(0, badge_y + BADGE_H + 4, left_w, INPUT_H))

        self._draw_right_panel(pygame.Rect(right_x, 0, right_w, usable_h))
        self._draw_status_overlay()
        self._draw_nav_bar(pygame.Rect(0, usable_h, WINDOW_W, NAV_BAR_H))

    def _draw_location_bar(self, rect: pygame.Rect) -> None:
        tint = LOCATION_TINTS.get(self._active_location_id, (30, 30, 30))
        pygame.draw.rect(self._screen, tint, rect)
        name = LOCATION_DISPLAY_NAMES.get(self._active_location_id, self._active_location_id)
        txt = self._font_loc.render(name, True, (220, 210, 180))
        self._screen.blit(txt, (rect.x + 10, rect.centery - txt.get_height() // 2))

    def _draw_right_panel(self, rect: pygame.Rect) -> None:
        surface, last_updated = self._graph_poller.get_surface()
        if surface is None:
            pygame.draw.rect(self._screen, _CLR_RIGHT_PLACEHOLDER, rect)
            msg = self._font_nav.render("Waiting for data…", True, _CLR_PLACEHOLDER_TEXT)
            self._screen.blit(msg, (
                rect.centerx - msg.get_width() // 2,
                rect.centery - msg.get_height() // 2,
            ))
            return
        self._screen.blit(surface, rect.topleft)
        if last_updated:
            ts = self._font_nav.render(f"Updated: {last_updated}", True, _CLR_TIMESTAMP)
            self._screen.blit(ts, (rect.right - ts.get_width() - 6, rect.bottom - ts.get_height() - 4))

    def _draw_status_overlay(self) -> None:
        if self._active_npc_id:
            self._relation_ticker.tick(self._active_npc_id)
            delta_text = self._relation_ticker.get_delta_text(self._active_npc_id)
            if delta_text:
                rel_surf = self._font_nav.render(delta_text, True, (120, 200, 240))
                self._screen.blit(rel_surf, (8, WINDOW_H - NAV_BAR_H - 52))
        if self._sandbox_loop is not None:
            on = self._sandbox_loop.is_running
            label = "AUTO-TICK: ON" if on else "AUTO-TICK: OFF"
            color = (200, 140, 30) if on else (90, 90, 110)
            tick_surf = self._font_nav.render(label, True, color)
            self._screen.blit(tick_surf, (8, WINDOW_H - NAV_BAR_H - 36))
        if not self._status_text or time.monotonic() > self._status_until:
            return
        surf = self._font_nav.render(self._status_text, True, (240, 230, 80))
        self._screen.blit(surf, (8, WINDOW_H - NAV_BAR_H - 20))

    def _draw_nav_bar(self, rect: pygame.Rect) -> None:
        pygame.draw.rect(self._screen, _CLR_NAV_BG, rect)
        btn_w = rect.width // len(LOCATIONS)
        for i, loc_id in enumerate(LOCATIONS):
            btn_rect = pygame.Rect(rect.x + i * btn_w, rect.y, btn_w - 2, rect.height)
            active = loc_id == self._active_location_id
            pygame.draw.rect(
                self._screen,
                _CLR_NAV_BTN_ACTIVE if active else _CLR_NAV_BTN,
                btn_rect,
                border_radius=4,
            )
            label = LOCATION_DISPLAY_NAMES.get(loc_id, loc_id)
            txt = self._font_nav.render(label, True, _CLR_NAV_TEXT)
            self._screen.blit(
                txt,
                (btn_rect.centerx - txt.get_width() // 2, btn_rect.centery - txt.get_height() // 2),
            )


def run() -> None:
    """Instantiate the game window from default config and run it."""
    cfg = DemoConfig()
    client = EngineClient(
        base_url=cfg.NPC_BASE_URL,
        api_key=cfg.NPC_API_KEY,
        dialogue_timeout=cfg.NPC_DIALOGUE_TIMEOUT_S,
        graph_timeout=cfg.NPC_GRAPH_TIMEOUT_S,
    )
    GameWindow(client, cfg).run()
