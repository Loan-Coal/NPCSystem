"""
Module: game_window
Layer: demo_game.ui
Purpose: Main pygame game window — thin coordinator. Owns the event loop and
         routes inputs to LeftPanelRenderer / RightPanelRenderer.
         Thread orchestration, queue dispatch, and quest/trade handlers live in
         game_controller.py (extracted per ISSUE-045 / DEC-032).
Dependencies: pygame, demo_game.client, demo_game.config, demo_game.constants,
              demo_game.game_controller, demo_game.emotion_poller,
              demo_game.graph_panel.poller, demo_game.world_state_poller,
              demo_game.ui.left_panel, demo_game.ui.right_panel
Used by: demo_game.__main__
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pygame

from demo_game.client import EngineClient, EngineClientError
from demo_game.config import DemoConfig
from demo_game.constants import LOCATION_DISPLAY_NAMES, LOCATION_NPC_MAP, LOCATIONS, NPC_LOCATION_MAP, PALETTE
from demo_game.game_controller import ControllerCallbacks, GameController
from demo_game.emotion_poller import EmotionPoller
from demo_game.graph_panel.poller import GraphPoller
from demo_game.world_state_poller import WorldStatePoller
from demo_game.ui.font_loader import FontLoader
from demo_game.ui.left_panel import LeftPanelRenderer
from demo_game.ui.right_panel import RightPanelRenderer

_LEFT_PANEL_RATIO = 0.60
_NAV_BAR_H = 48
_FPS = 30

_CLR_BG = PALETTE["bg"]
_CLR_NAV_BG = (14, 14, 20)
_CLR_NAV_BTN = (38, 38, 52)
_CLR_NAV_BTN_ACTIVE = (70, 90, 155)
_CLR_NAV_TEXT = (200, 200, 210)


class GameWindow:
    """Main game window — event loop and panel coordination.

    Args:
        client: Initialised EngineClient.
        cfg: Demo runtime configuration.
        window_w: Window width in pixels (default 1280).
        window_h: Window height in pixels (default 720).
    """

    def __init__(self, client: EngineClient, cfg: DemoConfig, window_w: int = 1280, window_h: int = 720) -> None:
        self._client = client
        self._cfg = cfg
        self._window_w = window_w
        self._window_h = window_h

        self._left_w = int(window_w * _LEFT_PANEL_RATIO)
        self._right_x = self._left_w + 4
        self._right_w = window_w - self._right_x
        self._right_h = window_h - _NAV_BAR_H
        self._usable_h = window_h - _NAV_BAR_H

        self._active_location_id: str = LOCATIONS[0]
        self._active_npc_id: str = LOCATION_NPC_MAP[LOCATIONS[0]][0]
        self._status_text: str = ""
        self._status_until: float = 0.0

        pygame.init()
        self._screen = pygame.display.set_mode((window_w, window_h))
        pygame.display.set_caption("NPC Engine — Demo")

        font_body = FontLoader.get(14)
        font_label = FontLoader.get(12)
        font_nav = FontLoader.get(14)
        font_loc = FontLoader.get(16)
        self._font_nav = font_nav

        self._left = LeftPanelRenderer(font_body, font_label, font_nav, font_loc)
        self._left.setup(self._active_location_id, self._active_npc_id)

        self._graph_poller = GraphPoller(client, cfg, self._right_w, self._right_h)
        self._right = RightPanelRenderer(self._graph_poller, font_nav, font_body, font_label)
        self._graph_poller.start()

        self._world_state_poller = WorldStatePoller(client, interval_s=2.0)
        self._world_state_poller.start()

        self._emotion_poller = EmotionPoller(client, interval_s=5.0)
        self._emotion_poller.set_active_npc(self._active_npc_id)
        self._emotion_poller.start()

        self._ctrl = GameController(
            client,
            cfg.DEMO_PLAYER_ID,
            ControllerCallbacks(
                on_npc_response=lambda npc, turn, color: self._left.add_npc_response(
                    npc, turn.npc_text, turn.degradation_level, turn.emotion, color
                ),
                on_error=lambda npc, msg: self._left.add_error(npc, msg),
                on_sidebar_data=lambda name, data: self._right.set_sidebar_data(name, data),
                on_clear_sidebar=self._right.clear_sidebar,
                on_set_status=self._set_status,
            ),
        )

        _quest_cache = Path(".cache/demo/aldric_quest.json")
        if _quest_cache.exists():
            try:
                self._ctrl.quest_id = json.loads(_quest_cache.read_text())["quest_id"]
                self._right.set_quest(client.get_quest(self._ctrl.quest_id))
            except Exception:
                pass

        self._right.set_quest_accept_callback(lambda: self._ctrl.on_quest_accept(self._right))
        self._right.set_quest_complete_callback(lambda: self._ctrl.on_quest_complete(self._active_npc_id, self._right))
        self._right.set_quest_reward_callback(lambda: self._ctrl.on_quest_reward(self._right))

        self._right.set_npc_selected(bool(self._active_npc_id))
        self._right.set_generate_quest_callback(
            lambda: self._ctrl.spawn_quest_generate(self._active_npc_id)
        )
        self._right.set_inspect_callback(
            lambda: self._ctrl.spawn_inspect(self._active_npc_id)
        )
        self._right.set_give_item_callback(
            lambda: self._right.start_item_pick(
                lambda item: self._ctrl.on_give_item(self._active_npc_id, item, self._right)
            )
        )
        self._right.set_travel_callback(self._on_travel_clicked)
        self._right.set_bribe_callback(
            lambda: self._ctrl.spawn_bribe(self._active_npc_id)
        )

        self._right.set_trade_offer_callback(
            lambda: self._ctrl.on_trade_offer(self._ctrl.active_npc_id_for_trade or self._active_npc_id, self._right)
        )
        self._right.set_trade_confirm_callback(
            lambda: self._ctrl.on_trade_confirm(self._ctrl.active_npc_id_for_trade or self._active_npc_id, self._right)
        )

        try:
            self._right.set_chain_data(client.get_graph_edges("KNOWS_ABOUT", dst_id="northern_war_begins"))
        except Exception:
            pass

        try:
            self._right.set_inventory(client.get_items_for_character(cfg.DEMO_PLAYER_ID))
            char = client.get_node("Character", cfg.DEMO_PLAYER_ID)
            self._right.set_player_gold((char or {}).get("currency_balance"))
        except EngineClientError as exc:
            print(f"[inventory] startup fetch failed: {exc}", file=sys.stderr)

    def run(self) -> None:
        """Start the game loop. Blocks until the window is closed."""
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                self._handle_event(event)
            self._ctrl.poll_response_queue(self._active_npc_id, self._right)
            self._ctrl.poll_sidebar_queue()
            self._ctrl.poll_generate_quest_queue(self._right)
            self._ctrl.poll_inspect_queue(self._right)
            self._ctrl.poll_travel_queue()
            self._ctrl.poll_bribe_queue()
            self._left.set_waiting(self._ctrl.is_waiting)
            self._render()
            pygame.display.flip()
            clock.tick(_FPS)
        pygame.quit()

    def _handle_event(self, event: pygame.event.Event) -> None:
        preset = self._left.handle_action_bar(event)
        if preset is not None:
            self._left.input.set_text(preset)

        submitted = self._left.input.handle_event(event)
        if submitted:
            npc_id = self._left.npc_list.active_id or self._active_npc_id
            self._left.add_player_message(npc_id, submitted)
            self._ctrl.submit_dialogue(submitted, npc_id, self._active_location_id)

        if self._right.show_sidebar:
            self._right.handle_scroll(event)
        elif self._right.show_quest_panel:
            self._right.handle_quest_click(event)
        elif self._right.show_trade_panel:
            self._right.handle_trade_click(event)
        elif self._right.show_inventory_panel:
            self._right.handle_inventory_event(event)
        elif self._right.show_actions_panel:
            self._right.handle_actions_event(event)
        elif self._right.show_inspect_panel:
            self._right.handle_scroll(event)
        elif self._active_npc_id:
            self._left.handle_scroll(event)

        clicked_npc = self._left.npc_list.handle_event(event)
        if clicked_npc:
            self._active_npc_id = clicked_npc
            self._left.set_active_npc(clicked_npc)
            self._ctrl.spawn_sidebar_fetch(clicked_npc)
            self._emotion_poller.set_active_npc(clicked_npc)
            self._right.set_npc_selected(True)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_nav_click(event.pos)
        if event.type == pygame.KEYDOWN:
            self._handle_key(event.key)

    def _set_active_location(self, loc_id: str) -> None:
        """Switch active location, update left panel, and trigger travel API call."""
        if loc_id == self._active_location_id:
            self._ctrl.spawn_travel(loc_id)
            return
        self._active_location_id = loc_id
        npcs = LOCATION_NPC_MAP[loc_id]
        self._active_npc_id = npcs[0]
        self._left.set_location(loc_id, npcs[0])
        self._emotion_poller.set_active_npc(npcs[0])
        self._right.set_npc_selected(True)
        self._ctrl.spawn_travel(loc_id)

    def _handle_nav_click(self, pos: tuple[int, int]) -> None:
        if pos[1] < self._window_h - _NAV_BAR_H:
            return
        idx = pos[0] // (self._window_w // len(LOCATIONS))
        if 0 <= idx < len(LOCATIONS):
            self._set_active_location(LOCATIONS[idx])

    def _on_travel_clicked(self) -> None:
        """Travel button handler: move player to the selected NPC's home location."""
        loc_id = NPC_LOCATION_MAP.get(self._active_npc_id)
        if loc_id:
            self._set_active_location(loc_id)

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
        elif key == pygame.K_TAB:
            self._right.cycle_tab()

    def _render(self) -> None:
        self._screen.fill(_CLR_BG)
        epoch, conditions = self._world_state_poller.get_state()
        new_conds = self._world_state_poller.pop_new_conditions()
        if new_conds:
            self._left.show_event_banner(new_conds[0])
        self._left.set_emotion(*self._emotion_poller.get_emotion())
        self._left.draw(self._screen, self._left_w, self._usable_h, epoch, conditions)
        self._right.draw(self._screen, pygame.Rect(self._right_x, 0, self._right_w, self._usable_h))
        self._draw_status_overlay()
        self._draw_nav_bar(pygame.Rect(0, self._usable_h, self._window_w, _NAV_BAR_H))

    def _draw_status_overlay(self) -> None:
        if not self._status_text or time.monotonic() > self._status_until:
            return
        surf = self._font_nav.render(self._status_text, True, (240, 230, 80))
        self._screen.blit(surf, (8, self._window_h - _NAV_BAR_H - 20))

    def _draw_nav_bar(self, rect: pygame.Rect) -> None:
        pygame.draw.rect(self._screen, _CLR_NAV_BG, rect)
        btn_w = rect.width // len(LOCATIONS)
        for i, loc_id in enumerate(LOCATIONS):
            btn_rect = pygame.Rect(rect.x + i * btn_w, rect.y, btn_w - 2, rect.height)
            active = loc_id == self._active_location_id
            pygame.draw.rect(self._screen, _CLR_NAV_BTN_ACTIVE if active else _CLR_NAV_BTN, btn_rect, border_radius=4)
            label = LOCATION_DISPLAY_NAMES.get(loc_id, loc_id)
            txt = self._font_nav.render(label, True, _CLR_NAV_TEXT)
            self._screen.blit(txt, (btn_rect.centerx - txt.get_width() // 2, btn_rect.centery - txt.get_height() // 2))

    def _set_status(self, text: str, duration: float = 2.0) -> None:
        self._status_text = text
        self._status_until = time.monotonic() + duration


def run(window_w: int = 1280, window_h: int = 720) -> None:
    """Instantiate the game window from default config and run the event loop."""
    cfg = DemoConfig()
    client = EngineClient(
        base_url=cfg.NPC_BASE_URL, api_key=cfg.NPC_API_KEY,
        dialogue_timeout=cfg.NPC_DIALOGUE_TIMEOUT_S, graph_timeout=cfg.NPC_GRAPH_TIMEOUT_S,
    )
    GameWindow(client, cfg, window_w=window_w, window_h=window_h).run()
