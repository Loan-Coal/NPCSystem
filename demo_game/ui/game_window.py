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
              demo_game.npc_politics_poller, demo_game.npc_initiative_poller,
              demo_game.npc_player_model_poller, demo_game.director_beat_poller,
              demo_game.pledge_poller, demo_game.treaty_poller,
              demo_game.chapter_poller, demo_game.tension_poller,
              demo_game.intent_ui, demo_game.sandbox_loop,
              demo_game.ui.left_panel, demo_game.ui.right_panel,
              demo_game.ui.relation_ticker
Used by: demo_game.__main__
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

_now = time.monotonic
from typing import TYPE_CHECKING

import pygame

from demo_game.client import EngineClient, EngineClientError
from demo_game.config import DemoConfig, get_demo_config
from demo_game.constants import LOCATION_DISPLAY_NAMES, LOCATION_NPC_MAP, LOCATIONS, NPC_DISPLAY_NAMES, NPC_LOCATION_MAP, PALETTE
from demo_game.game_end_checker import ARC_WIN_SUBTITLES, LOSE_SUBTITLES, WIN_PATH_SUBTITLES
from demo_game.game_controller import ControllerCallbacks, GameController
from demo_game.game_end_poller import GameEndPoller
from demo_game.gold_poller import GoldPoller
from demo_game.emotion_poller import EmotionPoller
from demo_game.graph_panel.poller import GraphPoller
from demo_game.intent_ui import INTENT_BUBBLE_DISPLAY_SECONDS, INTENT_POLL_INTERVAL_SECONDS, TRIGGER_PHRASES
from demo_game.npc_initiative_poller import NpcInitiativePoller
from demo_game.npc_needs_poller import NpcNeedsPoller
from demo_game.npc_goals_poller import NpcGoalsPoller
from demo_game.npc_memory_poller import NpcMemoryPoller
from demo_game.npc_player_model_poller import NpcPlayerModelPoller
from demo_game.npc_schemes_poller import NpcSchemesPoller
from demo_game.chapter_poller import ChapterPoller
from demo_game.director_beat_poller import DirectorBeatPoller
from demo_game.npc_politics_poller import NpcPoliticsPoller
from demo_game.pledge_poller import PledgePoller
from demo_game.tension_poller import TensionPoller
from demo_game.treaty_poller import TreatyPoller
from demo_game.world_poller import WorldPoller
from demo_game.world_state_poller import WorldStatePoller
from demo_game.ui.font_loader import FontLoader
from demo_game.ui.left_panel import LeftPanelRenderer
from demo_game.ui.relation_ticker import RelationTicker
from demo_game.ui.right_panel import RightPanelRenderer

if TYPE_CHECKING:
    from demo_game.sandbox_loop import SandboxLoop

_LEFT_PANEL_RATIO = 0.60
_NAV_BAR_H = 48
_FPS = 30

_CLR_BG = PALETTE["bg"]
_CLR_NAV_BG = (14, 14, 20)
_CLR_NAV_BTN = (38, 38, 52)
_CLR_NAV_BTN_ACTIVE = (70, 90, 155)
_CLR_NAV_TEXT = (200, 200, 210)

# G2.3 — director-beat cue
_CLR_DIRECTOR_BEAT = (180, 220, 255)  # Subtle blue-white for "something stirs…" cue.
_DIRECTOR_BEAT_CUE_SECONDS = 5.0  # How long the cue stays visible.

# H3.4 — chapter/act banner colour
_CLR_CHAPTER_BANNER = (200, 180, 100)
# H3.5 — tension HUD colours
_CLR_TENSION_LOW = (80, 180, 80)
_CLR_TENSION_MID = (200, 160, 40)
_CLR_TENSION_HIGH = (200, 60, 40)
# Severity threshold: >= this value renders in high-tension colour.
_TENSION_HIGH_THRESHOLD = 7
# Severity threshold: >= this value renders in mid-tension colour.
_TENSION_MID_THRESHOLD = 4

# Game-end overlay colours.
_CLR_OVERLAY_WIN_BG = (10, 50, 20, 210)
_CLR_OVERLAY_LOSE_BG = (60, 10, 10, 210)
_CLR_OVERLAY_WIN_TEXT = (60, 230, 90)
_CLR_OVERLAY_LOSE_TEXT = (230, 60, 60)
_CLR_OVERLAY_SUB = (200, 200, 200)

_logger = logging.getLogger(__name__)


class GameWindow:
    """Main game window — event loop and panel coordination.

    Args:
        client: Initialised EngineClient.
        cfg: Demo runtime configuration.
        window_w: Window width in pixels (default 1280).
        window_h: Window height in pixels (default 720).
        sandbox_loop: Optional auto-tick loop; toggleable with S key.
    """

    def __init__(
        self,
        client: EngineClient,
        cfg: DemoConfig,
        window_w: int = 1280,
        window_h: int = 720,
        sandbox_loop: SandboxLoop | None = None,
    ) -> None:
        self._client = client
        self._cfg = cfg
        self._window_w = window_w
        self._window_h = window_h
        self._sandbox_loop = sandbox_loop

        self._left_w = int(window_w * _LEFT_PANEL_RATIO)
        self._right_x = self._left_w + 4
        self._right_w = window_w - self._right_x
        self._right_h = window_h - _NAV_BAR_H
        self._usable_h = window_h - _NAV_BAR_H

        self._active_location_id: str = LOCATIONS[0]
        self._active_npc_id: str = LOCATION_NPC_MAP[LOCATIONS[0]][0]
        self._status_text: str = ""
        self._status_until: float = 0.0
        self._game_over: bool = False
        self._game_over_outcome: str = ""  # "win" or "lose"
        self._running: bool = True
        self._intent_bubble_text: str = ""
        self._intent_bubble_npc: str = ""
        self._intent_bubble_until: float = 0.0
        # Last player message submitted — used for on-turn retrieval refresh (G1.2).
        self._last_player_message: str = ""

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
        # G1.3 — wire PART_OF edge fetcher so left panel can render breadcrumbs.
        self._left.set_graph_edges_fn(client.get_graph_edges)

        self._graph_poller = GraphPoller(client, cfg, self._right_w, self._right_h)
        self._right = RightPanelRenderer(self._graph_poller, font_nav, font_body, font_label)
        self._graph_poller.start()

        self._relation_ticker: RelationTicker = RelationTicker(client)

        self._world_state_poller = WorldStatePoller(client, interval_s=2.0)
        self._world_state_poller.start()

        self._game_end_poller = GameEndPoller(client, cfg.DEMO_PLAYER_ID, interval_s=3.0)
        self._game_end_poller.start()

        self._gold_poller = GoldPoller(client, cfg.DEMO_PLAYER_ID, interval_s=3.0)
        self._gold_poller.start()

        self._world_poller = WorldPoller(client, interval_s=5.0, event_limit=20)
        self._world_poller.start()

        self._emotion_poller = EmotionPoller(client, interval_s=5.0)
        self._emotion_poller.set_active_npc(self._active_npc_id)
        self._emotion_poller.start()

        self._needs_poller = NpcNeedsPoller(client, interval_s=5.0)
        self._needs_poller.set_active_npc(self._active_npc_id)
        self._needs_poller.start()

        self._goals_poller = NpcGoalsPoller(client, interval_s=5.0)
        self._goals_poller.set_active_npc(self._active_npc_id)
        self._goals_poller.start()

        self._politics_poller = NpcPoliticsPoller(client, interval_s=5.0)
        self._politics_poller.set_active_npc(self._active_npc_id)
        self._politics_poller.start()

        self._memory_poller = NpcMemoryPoller(client, interval_s=5.0)
        self._memory_poller.set_active_npc(self._active_npc_id)
        self._memory_poller.start()

        self._player_model_poller = NpcPlayerModelPoller(
            client, cfg.DEMO_PLAYER_ID, interval_s=5.0
        )
        self._player_model_poller.set_active_npc(self._active_npc_id)
        self._player_model_poller.start()

        self._schemes_poller = NpcSchemesPoller(client, interval_s=5.0)
        self._schemes_poller.set_active_npc(self._active_npc_id)
        self._schemes_poller.start()

        self._pledge_poller = PledgePoller(client, interval_s=5.0)
        self._pledge_poller.set_active_npc(self._active_npc_id)
        self._pledge_poller.start()
        self._right.set_oath_active_npc(self._active_npc_id)

        self._treaty_poller = TreatyPoller(client, interval_s=8.0)
        self._treaty_poller.start()

        self._chapter_poller = ChapterPoller(client, interval_s=10.0)
        self._chapter_poller.start()

        self._tension_poller = TensionPoller(client, interval_s=4.0)
        self._tension_poller.start()

        self._director_beat_poller = DirectorBeatPoller(client, interval_s=4.0)
        self._director_beat_poller.start()

        # G2.3 — director-beat cue state
        self._director_beat_cue_text: str = ""
        self._director_beat_cue_until: float = 0.0

        self._initiative_poller = NpcInitiativePoller(
            client, cfg.DEMO_PLAYER_ID, interval_s=INTENT_POLL_INTERVAL_SECONDS
        )
        self._initiative_poller.start()

        self._ctrl = GameController(
            client,
            cfg.DEMO_PLAYER_ID,
            ControllerCallbacks(
                on_npc_response=lambda npc, turn, color: self._on_npc_response(npc, turn, color),
                on_error=lambda npc, msg: self._left.add_error(npc, msg),
                on_sidebar_data=lambda name, data: self._right.set_sidebar_data(name, data),
                on_clear_sidebar=self._right.clear_sidebar,
                on_set_status=self._set_status,
                on_stream_begin=lambda npc: self._left.begin_streaming_npc_response(npc),
                on_npc_token=lambda npc, chunk: self._left.append_npc_token(npc, chunk),
                on_stream_done=lambda npc, turn, color: self._on_stream_done(npc, turn, color),
                on_facial_expression=lambda npc, expr: self._left.set_facial_expression(expr),
            ),
            ws_url=client.ws_url,
            ws_api_key=client.api_key,
        )

        _quest_cache = Path(".cache/demo/aldric_quest.json")
        if _quest_cache.exists():
            try:
                self._ctrl.quest_id = json.loads(_quest_cache.read_text())["quest_id"]
                self._right.set_quest(client.get_quest(self._ctrl.quest_id))
            except Exception as exc:
                _logger.warning("quest cache restore failed: %s", exc)

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
        self._right.set_consolidate_memory_callback(
            lambda: self._ctrl.spawn_consolidate_memory(self._active_npc_id)
        )
        self._right.set_spread_rumor_callback(
            lambda: self._ctrl.spawn_spread_rumor(self._active_npc_id)
        )
        self._right.set_correct_rumor_callback(
            lambda: self._ctrl.spawn_correct_rumor(self._active_npc_id)
        )

        # H3.1 — oath panel callbacks
        self._right.set_oath_swear_callback(self._on_oath_swear)
        self._right.set_oath_break_callback(self._on_oath_break)

        # H3.2 — treaty panel callbacks
        self._right.set_treaty_broker_callback(self._on_treaty_broker)
        self._right.set_treaty_break_callback(self._on_treaty_break)

        # H3.3 — investigation panel callback
        self._right.set_investigate_callback(self._on_investigate)

        self._right.set_trade_offer_callback(
            lambda: self._ctrl.on_trade_offer(self._ctrl.active_npc_id_for_trade or self._active_npc_id, self._right)
        )
        self._right.set_trade_confirm_callback(
            lambda: self._ctrl.on_trade_confirm(self._ctrl.active_npc_id_for_trade or self._active_npc_id, self._right)
        )

        try:
            self._right.set_chain_data(client.get_graph_edges("KNOWS_ABOUT", dst_id="northern_war_begins"))
        except Exception as exc:
            _logger.warning("gossip chain fetch failed: %s", exc)

        try:
            self._right.set_inventory(client.get_items_for_character(cfg.DEMO_PLAYER_ID))
        except EngineClientError as exc:
            _logger.warning("inventory startup fetch failed: %s", exc)

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
                    self._running = False
                self._handle_event(event)
            self._ctrl.poll_response_queue(self._active_npc_id, self._right)
            self._ctrl.poll_token_queue(self._active_npc_id, self._right)
            self._ctrl.poll_sidebar_queue()
            self._ctrl.poll_generate_quest_queue(self._right)
            self._ctrl.poll_inspect_queue(self._right)
            self._ctrl.poll_travel_queue()
            self._ctrl.poll_bribe_queue()
            self._ctrl.poll_spread_rumor_queue()
            self._ctrl.poll_correct_rumor_queue()
            self._ctrl.poll_consolidate_memory_queue(
                on_created=lambda _: self._memory_poller.refresh()
            )
            self._poll_intent_queue()
            self._left.set_waiting(self._ctrl.is_waiting)
            self._render()
            pygame.display.flip()
            clock.tick(_FPS)
        pygame.quit()

    # ------------------------------------------------------------------
    # Dialogue turn callbacks (G1.1 / G1.2 / G1.4)
    # ------------------------------------------------------------------

    def _on_npc_response(self, npc_id: str, turn: object, color: tuple) -> None:
        """Handle a completed REST-path dialogue turn.

        Forwards the NPC response to the left panel, then triggers
        on-turn retrieval and relationship-phase refreshes.

        Args:
            npc_id: Responding NPC identifier.
            turn: Parsed DialogueTurn from the REST response.
            color: Degradation badge colour tuple.
        """
        self._left.add_npc_response(
            npc_id, turn.npc_text, turn.degradation_level, turn.emotion, color  # type: ignore[attr-defined]
        )
        self._refresh_retrieval(npc_id)
        self._refresh_relationship_phase(npc_id)

    def _on_stream_done(self, npc_id: str, turn: object, color: tuple) -> None:
        """Handle a completed WS-streaming dialogue turn.

        Updates the degradation badge then triggers retrieval and
        relationship-phase refreshes.

        Args:
            npc_id: Responding NPC identifier.
            turn: Parsed DialogueTurn from WS streaming metadata.
            color: Degradation badge colour tuple.
        """
        self._left.update_badge(
            turn.degradation_level, turn.emotion, color  # type: ignore[attr-defined]
        )
        self._refresh_retrieval(npc_id)
        self._refresh_relationship_phase(npc_id)

    def _refresh_retrieval(self, npc_id: str) -> None:
        """Fetch and push updated retrieval context for npc_id + last player query.

        Called on-turn (after each dialogue done event). Failures are swallowed
        and logged — retrieval is cosmetic, never crash the render loop.

        Args:
            npc_id: Active NPC whose retrieval context to fetch.
        """
        query = self._last_player_message
        if not query:
            return
        try:
            payload = self._client.get_retrieval_debug(npc_id, query)
            self._right.set_retrieval_payload(payload)
        except Exception as exc:
            _logger.warning("retrieval refresh failed npc=%s: %s", npc_id, exc)

    def _refresh_relationship_phase(self, npc_id: str) -> None:
        """Fetch and set the relationship phase for npc_id ↔ player.

        Failures are swallowed and logged so a missing relationship node
        never crashes the render loop.

        Args:
            npc_id: NPC whose relationship with the player to fetch.
        """
        try:
            data = self._client.get_relationship(npc_id, self._cfg.DEMO_PLAYER_ID)
            phase = data.get("relationship_phase") if data else None
            self._left.set_relationship_phase(phase)
        except Exception as exc:
            _logger.warning("relationship phase fetch failed npc=%s: %s", npc_id, exc)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _handle_event(self, event: pygame.event.Event) -> None:
        preset = self._left.handle_action_bar(event)
        if preset is not None:
            self._left.input.set_text(preset)

        submitted = self._left.input.handle_event(event)
        if submitted and not self._game_over:
            npc_id = self._left.npc_list.active_id or self._active_npc_id
            self._last_player_message = submitted  # G1.2 — track for retrieval refresh
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
        elif self._right.show_world_panel:
            self._right.handle_scroll(event)
        elif self._right.show_oath_panel:
            self._right.handle_oath_event(event)
        elif self._right.show_treaty_panel:
            self._right.handle_treaty_event(event)
        elif self._right.show_investigation_panel:
            self._right.handle_investigation_event(event)
        elif self._active_npc_id:
            self._left.handle_scroll(event)

        clicked_npc = self._left.npc_list.handle_event(event)
        if clicked_npc and clicked_npc != self._active_npc_id:
            self._relation_ticker.reset_baseline(self._active_npc_id)
            self._active_npc_id = clicked_npc
            self._left.set_active_npc(clicked_npc)
            self._ctrl.spawn_sidebar_fetch(clicked_npc)
            self._emotion_poller.set_active_npc(clicked_npc)
            self._needs_poller.set_active_npc(clicked_npc)
            self._goals_poller.set_active_npc(clicked_npc)
            self._politics_poller.set_active_npc(clicked_npc)
            self._memory_poller.set_active_npc(clicked_npc)
            self._player_model_poller.set_active_npc(clicked_npc)
            self._schemes_poller.set_active_npc(clicked_npc)
            self._pledge_poller.set_active_npc(clicked_npc)
            self._right.set_oath_active_npc(clicked_npc)
            self._right.set_npc_selected(True)
            self._refresh_relationship_phase(clicked_npc)  # G1.4 — update phase on NPC switch

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_nav_click(event.pos)
        if event.type == pygame.KEYDOWN:
            self._handle_key(event.key)

    def _handle_nav_click(self, pos: tuple[int, int]) -> None:
        if pos[1] < self._window_h - _NAV_BAR_H:
            return
        idx = pos[0] // (self._window_w // len(LOCATIONS))
        if 0 <= idx < len(LOCATIONS):
            self._set_active_location(LOCATIONS[idx])

    def _handle_key(self, key: int) -> None:
        if key == pygame.K_q and self._game_over and self._running:
            pygame.event.post(pygame.event.Event(pygame.QUIT))
            return
        if self._game_over:
            return
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

    def _set_active_location(self, loc_id: str) -> None:
        """Switch active location, update left panel, and trigger travel API call."""
        if loc_id == self._active_location_id:
            self._ctrl.spawn_travel(loc_id)
            return
        self._relation_ticker.reset_baseline(self._active_npc_id)
        self._active_location_id = loc_id
        npcs = LOCATION_NPC_MAP[loc_id]
        self._active_npc_id = npcs[0]
        self._left.set_location(loc_id, npcs[0])
        self._emotion_poller.set_active_npc(npcs[0])
        self._needs_poller.set_active_npc(npcs[0])
        self._goals_poller.set_active_npc(npcs[0])
        self._politics_poller.set_active_npc(npcs[0])
        self._memory_poller.set_active_npc(npcs[0])
        self._player_model_poller.set_active_npc(npcs[0])
        self._schemes_poller.set_active_npc(npcs[0])
        self._pledge_poller.set_active_npc(npcs[0])
        self._right.set_oath_active_npc(npcs[0])
        self._right.set_npc_selected(True)
        self._ctrl.spawn_travel(loc_id)
        self._refresh_relationship_phase(npcs[0])  # G1.4 — update phase on location change

    def _on_travel_clicked(self) -> None:
        """Travel button handler: move player to the selected NPC's home location."""
        loc_id = NPC_LOCATION_MAP.get(self._active_npc_id)
        if loc_id:
            self._set_active_location(loc_id)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> None:
        self._screen.fill(_CLR_BG)
        epoch, conditions = self._world_state_poller.get_state()
        new_conds = self._world_state_poller.pop_new_conditions()
        if new_conds:
            self._left.show_event_banner(new_conds[0])
        _emo_label, _emo_valence, _emo_arousal = self._emotion_poller.get_emotion()
        self._left.set_emotion(_emo_label, _emo_valence)
        self._right.set_emotion(_emo_label, _emo_valence, _emo_arousal)
        self._right.set_needs(self._needs_poller.get_needs())
        self._right.set_goals(self._goals_poller.get_goals())
        self._right.set_politics(
            self._politics_poller.get_pledges(),
            self._politics_poller.get_leverage(),
        )
        self._right.set_memories(self._memory_poller.get_memories())
        self._right.set_world_engines(self._world_poller.get_engines())
        self._right.set_world_events(self._world_poller.get_events())
        gold = self._gold_poller.get_gold()
        self._left.set_player_gold(gold)
        self._right.set_player_gold(gold)
        objective_state = self._game_end_poller.get_state()
        self._right.set_objective_state(objective_state)
        self._right.set_player_model(self._player_model_poller.get_model())
        # G2.2 — intrigue board data push
        self._right.set_schemes(self._schemes_poller.get_schemes())
        # H3.1 — oath panel data push
        self._right.set_oath_pledges(self._pledge_poller.get_pledges())
        # H3.2 — treaty panel data push
        self._right.set_treaties(self._treaty_poller.get_treaties())
        self._poll_director_beat_cue()
        if not self._game_over and objective_state.outcome is not None:
            self._game_over = True
            self._game_over_outcome = objective_state.outcome
        self._left.draw(self._screen, self._left_w, self._usable_h, epoch, conditions)
        self._right.draw(self._screen, pygame.Rect(self._right_x, 0, self._right_w, self._usable_h))
        self._draw_status_overlay()
        self._draw_intent_bubble()
        self._draw_director_beat_cue()
        self._draw_chapter_banner()
        self._draw_tension_hud()
        if self._game_over:
            self._draw_game_over_overlay()
        self._draw_nav_bar(pygame.Rect(0, self._usable_h, self._window_w, _NAV_BAR_H))

    def _poll_intent_queue(self) -> None:
        """Drain pending NPC intents and queue the highest-score one as a bubble."""
        if time.monotonic() < self._intent_bubble_until:
            return
        intents = self._initiative_poller.pop_pending()
        if not intents:
            return
        best = max(intents, key=lambda i: i.get("score", 0.0))
        npc_id = best.get("npc_id", "")
        trigger_type = best.get("trigger_type", "")
        phrase = TRIGGER_PHRASES.get(trigger_type, "I'd like to talk...")
        display_name = NPC_DISPLAY_NAMES.get(npc_id, npc_id)
        self._intent_bubble_npc = npc_id
        self._intent_bubble_text = f"{display_name}: {phrase}"
        self._intent_bubble_until = time.monotonic() + INTENT_BUBBLE_DISPLAY_SECONDS
        self._apply_intent_highlight(npc_id, display_name)

    def _apply_intent_highlight(self, npc_id: str, display_name: str) -> None:
        """Highlight the intent NPC in the list and pre-fill the input box.

        Called when a proactive NPC-initiative bubble is shown so the player
        can respond immediately without manually selecting the NPC.

        Args:
            npc_id: Internal NPC identifier (e.g. ``captain_sorn``).
            display_name: Human-readable name shown in the input pre-fill.
        """
        self._left.npc_list._active_id = npc_id
        self._left.input.set_text(f"[{display_name}] ")

    def _draw_intent_bubble(self) -> None:
        """Render the NPC-initiative intent bubble if one is active."""
        if not self._intent_bubble_text or time.monotonic() > self._intent_bubble_until:
            return
        font = FontLoader.get(14)
        text_surf = font.render(self._intent_bubble_text, True, (255, 255, 180))
        padding = 10
        bubble_w = text_surf.get_width() + padding * 2
        bubble_h = text_surf.get_height() + padding * 2
        bubble_x = self._left_w // 2 - bubble_w // 2
        bubble_y = 12
        bubble_surf = pygame.Surface((bubble_w, bubble_h), pygame.SRCALPHA)
        bubble_surf.fill((30, 30, 50, 210))
        self._screen.blit(bubble_surf, (bubble_x, bubble_y))
        pygame.draw.rect(
            self._screen, (120, 140, 220),
            pygame.Rect(bubble_x, bubble_y, bubble_w, bubble_h),
            width=1, border_radius=4,
        )
        self._screen.blit(text_surf, (bubble_x + padding, bubble_y + padding))

    def _draw_status_overlay(self) -> None:
        if self._active_npc_id:
            self._relation_ticker.tick(self._active_npc_id)
            delta_text = self._relation_ticker.get_delta_text(self._active_npc_id)
            if delta_text:
                rel_surf = self._font_nav.render(delta_text, True, (120, 200, 240))
                self._screen.blit(rel_surf, (8, self._window_h - _NAV_BAR_H - 52))
        if self._sandbox_loop is not None:
            on = self._sandbox_loop.is_running
            label = "AUTO-TICK: ON" if on else "AUTO-TICK: OFF"
            color = (200, 140, 30) if on else (90, 90, 110)
            tick_surf = self._font_nav.render(label, True, color)
            self._screen.blit(tick_surf, (8, self._window_h - _NAV_BAR_H - 36))
        if not self._status_text or time.monotonic() > self._status_until:
            return
        surf = self._font_nav.render(self._status_text, True, (240, 230, 80))
        self._screen.blit(surf, (8, self._window_h - _NAV_BAR_H - 20))

    def _poll_director_beat_cue(self) -> None:
        """Consume a new director beat and set the transient HUD cue if present."""
        beat = self._director_beat_poller.pop_new_beat()
        if beat is None:
            return
        kind = beat.get("beat_kind", "")
        npc_id = beat.get("npc_id", "")
        msg = f"something stirs… [{kind}] {npc_id}"
        self._director_beat_cue_text = msg
        self._director_beat_cue_until = _now() + _DIRECTOR_BEAT_CUE_SECONDS

    def _draw_director_beat_cue(self) -> None:
        """Render the director-beat HUD cue if one is active."""
        if not self._director_beat_cue_text or _now() > self._director_beat_cue_until:
            return
        font = FontLoader.get(12)
        surf = font.render(self._director_beat_cue_text, True, _CLR_DIRECTOR_BEAT)
        self._screen.blit(surf, (self._right_x + 8, 4))

    # ------------------------------------------------------------------
    # H3.1 — Oath action handlers
    # ------------------------------------------------------------------

    def _on_oath_swear(self) -> None:
        """Handle [SWEAR] button: post a default protect pledge for the active NPC."""
        npc_id = self._active_npc_id
        if not npc_id:
            return
        try:
            self._client.post_pledge(
                pledger_id=npc_id,
                pledgee_id=self._cfg.DEMO_PLAYER_ID,
                pledge_type="protect",
                tick=0,
                severity=50,
            )
            self._set_status(f"Oath sworn: {npc_id} → protect player")
            self._pledge_poller.refresh()
        except Exception as exc:
            _logger.warning("oath swear error npc=%s: %s", npc_id, exc)
            self._set_status("Oath swear failed")

    def _on_oath_break(self, pledge: dict) -> None:
        """Handle [BREAK] button: break the selected pledge.

        Args:
            pledge: Pledge dict with pledgee_id and pledge_type keys.
        """
        npc_id = self._active_npc_id
        if not npc_id:
            return
        pledgee_id = str(pledge.get("pledgee_id", ""))
        pledge_type = str(pledge.get("pledge_type", ""))
        if not pledgee_id or not pledge_type:
            return
        try:
            self._client.break_pledge(
                character_id=npc_id,
                pledgee_id=pledgee_id,
                pledge_type=pledge_type,
                tick=0,
            )
            self._set_status(f"Oath broken: {pledge_type} → {pledgee_id}")
            self._pledge_poller.refresh()
        except Exception as exc:
            _logger.warning("oath break error npc=%s: %s", npc_id, exc)
            self._set_status("Oath break failed")

    # ------------------------------------------------------------------
    # H3.2 — Treaty action handlers
    # ------------------------------------------------------------------

    def _on_treaty_broker(self) -> None:
        """Handle [BROKER] button: create a sample non-aggression treaty."""
        try:
            self._client.create_treaty(
                parties=["merchants_guild", "city_guard"],
                terms_narrative="Demo non-aggression pact.",
                signed_at_tick=0,
            )
            self._set_status("Treaty brokered: Merchants ↔ City Guard")
            self._treaty_poller.refresh()
        except Exception as exc:
            _logger.warning("treaty broker error: %s", exc)
            self._set_status("Treaty broker failed")

    def _on_treaty_break(self, treaty: dict) -> None:
        """Handle [BREAK] button: break the selected treaty.

        Args:
            treaty: Treaty dict with id/treaty_id and parties keys.
        """
        treaty_id = str(treaty.get("id") or treaty.get("treaty_id", ""))
        if not treaty_id:
            return
        breaking_faction = (treaty.get("parties") or ["merchants_guild"])[0]
        try:
            self._client.break_treaty(
                treaty_id=treaty_id,
                breaking_faction_id=str(breaking_faction),
                tick=0,
            )
            self._set_status(f"Treaty broken: {treaty_id[:16]}")
            self._treaty_poller.refresh()
        except Exception as exc:
            _logger.warning("treaty break error: %s", exc)
            self._set_status("Treaty break failed")

    # ------------------------------------------------------------------
    # H3.3 — Investigation handler
    # ------------------------------------------------------------------

    def _on_investigate(self) -> None:
        """Fetch investigation data for the default crime event and push to panel."""
        npc_id = self._active_npc_id
        if not npc_id:
            return
        event_id = "northern_war_begins"  # Default demo crime event
        try:
            data = self._client.get_investigation(npc_id, event_id)
            self._right.set_investigation(data)
            self._right.set_investigation_event_id(event_id)
            self._set_status("Investigation loaded")
        except Exception as exc:
            _logger.warning("investigation fetch error: %s", exc)
            self._set_status("Investigation failed")

    # ------------------------------------------------------------------
    # H3.4 — Chapter act banner (HUD overlay)
    # ------------------------------------------------------------------

    def _draw_chapter_banner(self) -> None:
        """Render the current chapter/act as a HUD line below the director beat."""
        chapter = self._chapter_poller.get_chapter()
        if chapter is not None:
            name = str(chapter.get("name") or chapter.get("theme") or "")
            label = f"ACT: {name}"
        else:
            label = ""
        if not label:
            return
        font = FontLoader.get(12)
        surf = font.render(label, True, _CLR_CHAPTER_BANNER)
        self._screen.blit(surf, (self._right_x + 8, 18))

    # ------------------------------------------------------------------
    # H3.5 — Story-pacing tension HUD
    # ------------------------------------------------------------------

    def _draw_tension_hud(self) -> None:
        """Render live max_event_severity and quest_generation_rate as a tension bar."""
        severity, rate = self._tension_poller.get_tension()
        if severity >= _TENSION_HIGH_THRESHOLD:
            clr = _CLR_TENSION_HIGH
        elif severity >= _TENSION_MID_THRESHOLD:
            clr = _CLR_TENSION_MID
        else:
            clr = _CLR_TENSION_LOW
        font = FontLoader.get(12)
        label = f"TENSION  sev:{severity}  rate:{rate:.2f}"
        surf = font.render(label, True, clr)
        self._screen.blit(surf, (self._right_x + 8, 32))

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

    def _draw_game_over_overlay(self) -> None:
        """Draw a semi-transparent win/lose overlay over the full game area.

        H1: renders win_path, grade (on win), failure_reason (on lose),
        total_gold, and ticks_remaining from ObjectiveState.
        """
        is_win = self._game_over_outcome == "win"
        overlay_color = _CLR_OVERLAY_WIN_BG if is_win else _CLR_OVERLAY_LOSE_BG
        overlay = pygame.Surface((self._left_w, self._usable_h), pygame.SRCALPHA)
        overlay.fill(overlay_color)
        self._screen.blit(overlay, (0, 0))

        objective_state = self._game_end_poller.get_state()
        cx = self._left_w // 2
        cy = self._usable_h // 2

        self._draw_overlay_headline(is_win, objective_state, cx, cy)
        self._draw_overlay_subtitle(is_win, objective_state, cx, cy)
        self._draw_overlay_stats(objective_state, cx, cy)
        font_sub = FontLoader.get(16)
        hint_surf = font_sub.render("Press Q to quit", True, _CLR_OVERLAY_SUB)
        self._screen.blit(hint_surf, (cx - hint_surf.get_width() // 2, cy + 80))

    def _draw_overlay_headline(self, is_win: bool, state: object, cx: int, cy: int) -> None:
        """Render the VICTORY/DEFEATED headline with optional grade letter."""
        font_big = FontLoader.get(36)
        text_color = _CLR_OVERLAY_WIN_TEXT if is_win else _CLR_OVERLAY_LOSE_TEXT
        grade = getattr(state, "grade", None)
        if is_win and grade:
            headline = f"VICTORY!  [{grade}]"
        else:
            headline = "VICTORY!" if is_win else "DEFEATED"
        headline_surf = font_big.render(headline, True, text_color)
        self._screen.blit(headline_surf, (cx - headline_surf.get_width() // 2, cy - 60))

    def _draw_overlay_subtitle(self, is_win: bool, state: object, cx: int, cy: int) -> None:
        """Render the win-path or failure-reason subtitle line."""
        font_sub = FontLoader.get(16)
        if is_win:
            win_path = getattr(state, "win_path", None)
            arc_faction = getattr(state, "arc_faction", None)
            if win_path and win_path in WIN_PATH_SUBTITLES:
                sub = WIN_PATH_SUBTITLES[win_path]
            elif win_path == "faction":
                sub = ARC_WIN_SUBTITLES.get(arc_faction, ARC_WIN_SUBTITLES[None])
            else:
                sub = ARC_WIN_SUBTITLES.get(arc_faction, ARC_WIN_SUBTITLES[None])
        else:
            failure_reason = getattr(state, "failure_reason", None)
            sub = LOSE_SUBTITLES.get(failure_reason or "legion", LOSE_SUBTITLES["legion"])
        sub_surf = font_sub.render(sub, True, _CLR_OVERLAY_SUB)
        self._screen.blit(sub_surf, (cx - sub_surf.get_width() // 2, cy - 20))

    def _draw_overlay_stats(self, state: object, cx: int, cy: int) -> None:
        """Render gold and ticks-remaining stats below the subtitle."""
        font_sub = FontLoader.get(14)
        total_gold = getattr(state, "total_gold", None)
        ticks_remaining = getattr(state, "ticks_remaining", None)
        parts: list[str] = []
        if total_gold is not None:
            parts.append(f"Gold: {total_gold}")
        if ticks_remaining is not None:
            parts.append(f"Ticks left: {max(ticks_remaining, 0)}")
        if parts:
            stats_surf = font_sub.render("  |  ".join(parts), True, _CLR_OVERLAY_SUB)
            self._screen.blit(stats_surf, (cx - stats_surf.get_width() // 2, cy + 10))


def run(window_w: int = 1280, window_h: int = 720) -> None:
    """Instantiate the game window from default config and run the event loop."""
    cfg = get_demo_config()
    client = EngineClient(
        base_url=cfg.NPC_BASE_URL,
        api_key=cfg.NPC_API_KEY,
        dialogue_timeout=cfg.NPC_DIALOGUE_TIMEOUT_S,
        graph_timeout=cfg.NPC_GRAPH_TIMEOUT_S,
    )
    GameWindow(client, cfg, window_w=window_w, window_h=window_h).run()
