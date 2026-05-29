"""
Module: game_window
Layer: demo_game.ui
Purpose: Main pygame game window — thin coordinator. Owns the event loop, daemon
         threads, and routes inputs to LeftPanelRenderer / RightPanelRenderer.
         All left-panel rendering lives in left_panel.py; right-panel in right_panel.py.
Dependencies: pygame, demo_game.client, demo_game.config, demo_game.constants,
              demo_game.dialogue, demo_game.emotion_poller, demo_game.graph_panel.poller,
              demo_game.knowledge_sidebar_fetcher, demo_game.world_state_poller,
              demo_game.ui.left_panel, demo_game.ui.right_panel
Used by: demo_game.__main__
Split rationale: DEC-032. game_window.py exceeded the 472-line DEC-024 trigger. Panel
rendering extracted to left_panel.py and right_panel.py; GameWindow retains only the
event loop, threading model, and navigation logic.
"""

from __future__ import annotations

import json
import queue
import sys
import threading
import time
from pathlib import Path

import pygame

from demo_game.client import EngineClient, EngineClientError
from demo_game.config import DemoConfig
from demo_game.constants import LOCATION_DISPLAY_NAMES, LOCATION_NPC_MAP, LOCATIONS, PALETTE
from demo_game.dialogue import build_dialogue_payload, degradation_color, parse_dialogue_response
from demo_game.emotion_poller import EmotionPoller
from demo_game.graph_panel.poller import GraphPoller
from demo_game.knowledge_sidebar_fetcher import fetch_npc_knowledge
from demo_game.world_state_poller import WorldStatePoller
from demo_game.ui.font_loader import FontLoader
from demo_game.ui.left_panel import LeftPanelRenderer
from demo_game.ui.right_panel import RightPanelRenderer

# ---------------------------------------------------------------------------
# Fixed UI constants — these do not scale with window size.
# ---------------------------------------------------------------------------
_LEFT_PANEL_RATIO = 0.60
_NAV_BAR_H = 48
_FPS = 30

_CLR_BG = PALETTE["bg"]
_CLR_NAV_BG = (14, 14, 20)
_CLR_NAV_BTN = (38, 38, 52)
_CLR_NAV_BTN_ACTIVE = (70, 90, 155)
_CLR_NAV_TEXT = (200, 200, 210)


# ---------------------------------------------------------------------------
# Background worker functions
# ---------------------------------------------------------------------------

def _dialogue_worker(client: EngineClient, payload: dict, result_q: queue.Queue) -> None:
    """Call post_dialogue in a daemon thread and push the result or exception."""
    try:
        result_q.put(client.post_dialogue(**payload))
    except Exception as exc:
        result_q.put(exc)


def _fetch_sidebar_worker(
    client: EngineClient,
    npc_id: str,
    result_q: queue.Queue,
) -> None:
    """Fetch KNOWS_ABOUT pairs for npc_id and push (status, npc_id, data)."""
    try:
        pairs = fetch_npc_knowledge(client, npc_id)
        result_q.put(("ok", npc_id, pairs))
    except Exception as exc:
        result_q.put(("err", npc_id, exc))


# ---------------------------------------------------------------------------
# GameWindow
# ---------------------------------------------------------------------------

class GameWindow:
    """Main game window — event loop, threads, and panel coordination.

    Args:
        client: Initialised EngineClient.
        cfg: Demo runtime configuration.
        window_w: Window width in pixels (default 1280).
        window_h: Window height in pixels (default 720).
    """

    def __init__(
        self,
        client: EngineClient,
        cfg: DemoConfig,
        window_w: int = 1280,
        window_h: int = 720,
    ) -> None:
        self._client = client
        self._cfg = cfg
        self._window_w = window_w
        self._window_h = window_h

        # Derived layout attributes — all other code reads these, not WINDOW_W/H.
        self._left_w = int(window_w * _LEFT_PANEL_RATIO)
        self._right_x = self._left_w + 4
        self._right_w = window_w - self._right_x
        self._right_h = window_h - _NAV_BAR_H
        self._usable_h = window_h - _NAV_BAR_H

        self._response_q: queue.Queue = queue.Queue()
        self._sidebar_fetch_q: queue.Queue = queue.Queue()
        self._is_waiting = False
        self._pending_npc_id: str | None = None

        self._active_location_id: str = LOCATIONS[0]
        self._active_npc_id: str = LOCATION_NPC_MAP[LOCATIONS[0]][0]

        self._status_text: str = ""
        self._status_until: float = 0.0

        self._trade_fair_price: int | None = None
        self._trade_state: str = "idle"  # mirrors left_panel for client-side logic

        pygame.init()
        self._screen = pygame.display.set_mode((window_w, window_h))
        pygame.display.set_caption("NPC Engine — Demo")

        font_body = FontLoader.get(14)
        font_label = FontLoader.get(12)
        font_nav = FontLoader.get(14)
        font_loc = FontLoader.get(16)
        self._font_nav = font_nav

        # Panel renderers — own their widgets; GameWindow owns the pollers.
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

        # Load cached quest for PLAYER STATUS tab — non-fatal if absent or stale.
        _quest_cache = Path(".cache/demo/aldric_quest.json")
        self._quest_id: str | None = None
        quest_data: dict | None = None
        if _quest_cache.exists():
            try:
                self._quest_id = json.loads(_quest_cache.read_text())["quest_id"]
                quest_data = client.get_quest(self._quest_id)
            except Exception:
                pass

        if quest_data and quest_data.get("status") == "available" and self._quest_id:
            try:
                result = client.post_quest_offer(
                    self._quest_id, "aldric_merchant", "player"
                )
                quest_data = result.get("data", quest_data)
            except Exception:
                pass

        self._right.set_quest(quest_data)
        self._right.set_quest_accept_callback(self._on_quest_accept)

        # Pre-fetch the gossip chain for the CHAIN tab — non-fatal if absent.
        try:
            chain_edges = client.get_graph_edges(
                "KNOWS_ABOUT", dst_id="northern_war_begins"
            )
            self._right.set_chain_data(chain_edges)
        except Exception:
            pass

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
            self._poll_sidebar_queue()
            self._render()
            pygame.display.flip()
            clock.tick(_FPS)

        pygame.quit()

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _handle_event(self, event: pygame.event.Event) -> None:
        preset = self._left.handle_action_bar(event)
        if preset is not None:
            self._left.input.set_text(preset)
            if preset == "I'd like to trade." and self._active_npc_id == "aldric_merchant":
                self._handle_trade_click()

        submitted = self._left.input.handle_event(event)
        if submitted:
            self._submit_dialogue(submitted)

        # Exclusive scroll routing (DEC-027): right panel takes priority.
        if self._right.show_sidebar:
            self._right.handle_scroll(event)
        elif self._right.show_quest_panel:
            self._right.handle_quest_click(event)
        elif self._active_npc_id:
            self._left.handle_scroll(event)

        clicked_npc = self._left.npc_list.handle_event(event)
        if clicked_npc:
            self._active_npc_id = clicked_npc
            self._left.set_active_npc(clicked_npc)
            self._spawn_sidebar_fetch(clicked_npc)
            self._emotion_poller.set_active_npc(clicked_npc)
            self._reset_trade()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_nav_click(event.pos)

        if event.type == pygame.KEYDOWN:
            self._handle_key(event.key)

    def _handle_nav_click(self, pos: tuple[int, int]) -> None:
        nav_y = self._window_h - _NAV_BAR_H
        if pos[1] < nav_y:
            return
        btn_w = self._window_w // len(LOCATIONS)
        idx = pos[0] // btn_w
        if 0 <= idx < len(LOCATIONS):
            loc_id = LOCATIONS[idx]
            if loc_id != self._active_location_id:
                self._change_location(loc_id)

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

    def _handle_trade_click(self) -> None:
        """Drive the two-click Aldric trade flow (non-fatal — swallows all exceptions).

        Click 1 (state == idle): fetch fair price, offer 80%, show result overlay.
        Click 2 (state == offered_low): offer fair price, show result overlay.
        Click 3+ (state == accepted): no-op.
        """
        if self._trade_state == "accepted":
            return
        try:
            if self._trade_fair_price is None:
                price = self._client.get_item_price("spice", "aldric_merchant")
                if price is None:
                    return
                self._trade_fair_price = price
                self._left.set_trade_price(price)

            if self._trade_state == "idle":
                offered = int(self._trade_fair_price * 0.8)
            else:
                offered = self._trade_fair_price

            result = self._client.post_trade(
                buyer_id="player",
                seller_id="aldric_merchant",
                item_id="northern_spice_bundle",
                item_type="spice",
                offered_price=offered,
                tick=0,
            )
            self._left.apply_trade_result(result, offered, self._trade_fair_price)
            self._trade_state = self._left.get_trade_state()
        except Exception:
            pass

    def _reset_trade(self) -> None:
        """Reset the trade state machine — called when the active NPC changes."""
        self._trade_state = "idle"
        self._trade_fair_price = None
        self._left.reset_trade_state()

    def _on_quest_accept(self) -> None:
        """Callback fired by the [ACCEPT QUEST] button in the PLAYER STATUS tab."""
        if not self._quest_id:
            return
        try:
            self._client.post_quest_accept(self._quest_id, "player")
            self._right.set_quest_status("active")
        except Exception:
            pass

    def _set_status(self, text: str, duration: float = 2.0) -> None:
        self._status_text = text
        self._status_until = time.monotonic() + duration

    # ------------------------------------------------------------------
    # Location navigation
    # ------------------------------------------------------------------

    def _change_location(self, loc_id: str) -> None:
        self._active_location_id = loc_id
        npcs = LOCATION_NPC_MAP[loc_id]
        self._active_npc_id = npcs[0]
        self._left.set_location(loc_id, npcs[0])
        self._emotion_poller.set_active_npc(npcs[0])
        self._reset_trade()

    # ------------------------------------------------------------------
    # Dialogue — submit + background worker
    # ------------------------------------------------------------------

    def _submit_dialogue(self, text: str) -> None:
        if self._is_waiting:
            return
        npc_id = self._left.npc_list.active_id or self._active_npc_id
        payload = build_dialogue_payload(
            npc_id,
            text,
            player_id=self._cfg.DEMO_PLAYER_ID,
            location_id=self._active_location_id,
        )
        self._pending_npc_id = npc_id
        self._left.add_player_message(npc_id, text)
        self._left.set_waiting(True)
        self._is_waiting = True
        threading.Thread(
            target=_dialogue_worker,
            args=(self._client, payload, self._response_q),
            daemon=True,
        ).start()

    def _spawn_sidebar_fetch(self, npc_id: str) -> None:
        """Launch a background thread to fetch KNOWS_ABOUT data for npc_id."""
        threading.Thread(
            target=_fetch_sidebar_worker,
            args=(self._client, npc_id, self._sidebar_fetch_q),
            daemon=True,
        ).start()

    def _poll_sidebar_queue(self) -> None:
        """Drain one sidebar-fetch result and update the right panel."""
        try:
            status, npc_id, data = self._sidebar_fetch_q.get_nowait()
        except queue.Empty:
            return
        if status == "ok":
            name = LOCATION_DISPLAY_NAMES.get(npc_id, npc_id)
            self._right.set_sidebar_data(name, data)
        else:
            print(f"sidebar fetch error for {npc_id}: {data}", file=sys.stderr)
            self._right.clear_sidebar()

    def _poll_response_queue(self) -> None:
        """Drain one dialogue result and update the left panel."""
        try:
            item = self._response_q.get_nowait()
        except queue.Empty:
            return

        self._is_waiting = False
        self._left.set_waiting(False)
        npc_id = self._pending_npc_id or self._left.npc_list.active_id or self._active_npc_id

        if isinstance(item, (Exception, EngineClientError)):
            self._left.add_error(npc_id, str(item))
            return

        turn = parse_dialogue_response(item)
        color = degradation_color(turn.degradation_level)
        self._left.add_npc_response(npc_id, turn.npc_text, turn.degradation_level, turn.emotion, color)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> None:
        self._screen.fill(_CLR_BG)
        epoch, conditions = self._world_state_poller.get_state()
        new_conds = self._world_state_poller.pop_new_conditions()
        if new_conds:
            self._left.show_event_banner(new_conds[0])
        self._left.set_emotion(*self._emotion_poller.get_emotion())
        self._left.draw(self._screen, self._left_w, self._usable_h, epoch, conditions)
        self._right.draw(
            self._screen,
            pygame.Rect(self._right_x, 0, self._right_w, self._usable_h),
        )
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
                (btn_rect.centerx - txt.get_width() // 2,
                 btn_rect.centery - txt.get_height() // 2),
            )


def run(window_w: int = 1280, window_h: int = 720) -> None:
    """Instantiate the game window from default config and run the event loop."""
    cfg = DemoConfig()
    client = EngineClient(
        base_url=cfg.NPC_BASE_URL,
        api_key=cfg.NPC_API_KEY,
        dialogue_timeout=cfg.NPC_DIALOGUE_TIMEOUT_S,
        graph_timeout=cfg.NPC_GRAPH_TIMEOUT_S,
    )
    GameWindow(client, cfg, window_w=window_w, window_h=window_h).run()
