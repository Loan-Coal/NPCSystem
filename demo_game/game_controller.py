"""
Module: game_controller
Layer: demo_game
Purpose: Background-thread orchestration and queue dispatch for the demo game.
         Quest, trade, give-item, and travel action handlers; dialogue submission.
         Quest/trade handlers are delegated to QuestTradeController. Decoupled
         from pygame rendering so it can be unit-tested without a display.
Dependencies: demo_game.action_workers, demo_game.client, demo_game.dialogue,
              demo_game.constants, demo_game.quest_trade_controller,
              npc_engine.engines.interaction
Used by: demo_game.ui.game_window

NOTE: ~318 lines — accepted over the 300-line limit (see DEC-048). GameController
is a single cohesive class; splitting travel into a separate file would require
yet another delegation layer that adds no clarity.
"""

from __future__ import annotations

import queue
import sys
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from demo_game.action_workers import (
    bribe_worker,
    dialogue_worker,
    fetch_sidebar_worker,
    generate_quest_worker,
    inspect_worker,
    travel_worker,
)
from demo_game.client import EngineClient, EngineClientError
from demo_game.constants import LOCATION_DISPLAY_NAMES, NPC_FACTIONS
from demo_game.dialogue import (
    DialogueTurn,
    build_dialogue_payload,
    degradation_color,
    parse_dialogue_response,
)
from demo_game.quest_trade_controller import QuestTradeController
from npc_engine.engines.interaction import dispatch_interaction

if TYPE_CHECKING:
    from demo_game.ui.right_panel import RightPanelRenderer


@dataclass
class ControllerCallbacks:
    """Callbacks GameController fires when state changes require UI updates.

    All callbacks are called from the main pygame thread so they may safely
    call pygame APIs.
    """

    on_npc_response: Callable | None = None      # (npc_id, turn, color) -> None
    on_error: Callable | None = None             # (npc_id, message) -> None
    on_sidebar_data: Callable | None = None      # (display_name, data) -> None
    on_clear_sidebar: Callable | None = None     # () -> None
    on_set_status: Callable | None = None        # (text, duration) -> None


class GameController:
    """Manages background threads, queues, and interaction dispatch for the demo.

    Quest, trade, and give-item handlers are delegated to QuestTradeController.

    Args:
        client: Initialised EngineClient.
        player_id: Player ID string from DemoConfig.
        callbacks: Bound UI callbacks for each result type.
    """

    def __init__(
        self,
        client: EngineClient,
        player_id: str,
        callbacks: ControllerCallbacks,
    ) -> None:
        self._client = client
        self._player_id = player_id
        self._cb = callbacks

        self._response_q: queue.Queue = queue.Queue()
        self._sidebar_fetch_q: queue.Queue = queue.Queue()
        self._generate_quest_q: queue.Queue = queue.Queue()
        self._inspect_q: queue.Queue = queue.Queue()
        self._travel_q: queue.Queue = queue.Queue()
        self._bribe_q: queue.Queue = queue.Queue()
        self._is_waiting = False
        self._pending_npc_id: str | None = None
        self._last_submitted_message: str = ""

        self._qt = QuestTradeController(
            client=client,
            player_id=player_id,
            on_set_status=callbacks.on_set_status,
        )

    @property
    def is_waiting(self) -> bool:
        """True while a dialogue request is in-flight."""
        return self._is_waiting

    @property
    def quest_id(self) -> str | None:
        """Active quest ID (delegated to QuestTradeController)."""
        return self._qt.quest_id

    @quest_id.setter
    def quest_id(self, value: str | None) -> None:
        self._qt.quest_id = value

    @property
    def active_npc_id_for_trade(self) -> str | None:
        """Active NPC for trade (delegated to QuestTradeController)."""
        return self._qt.active_npc_id_for_trade

    @active_npc_id_for_trade.setter
    def active_npc_id_for_trade(self, value: str | None) -> None:
        self._qt.active_npc_id_for_trade = value

    # ------------------------------------------------------------------
    # Thread spawning
    # ------------------------------------------------------------------

    def submit_dialogue(self, text: str, npc_id: str, location_id: str | None) -> None:
        """Launch a background thread for POST /v1/dialogue. No-op if already waiting."""
        if self._is_waiting:
            return
        self._last_submitted_message = text
        payload = build_dialogue_payload(npc_id, text, player_id=self._player_id, location_id=location_id)
        self._pending_npc_id = npc_id
        self._is_waiting = True
        threading.Thread(
            target=dialogue_worker,
            args=(self._client, payload, self._response_q),
            daemon=True,
        ).start()

    def spawn_sidebar_fetch(self, npc_id: str) -> None:
        """Launch a background thread to fetch KNOWS_ABOUT data for npc_id."""
        threading.Thread(
            target=fetch_sidebar_worker,
            args=(self._client, npc_id, self._sidebar_fetch_q),
            daemon=True,
        ).start()

    def spawn_quest_generate(self, npc_id: str) -> None:
        """Launch a background thread for POST /v1/admin/quests/generate."""
        threading.Thread(
            target=generate_quest_worker,
            args=(self._client, npc_id, self._generate_quest_q),
            daemon=True,
        ).start()

    def spawn_inspect(self, npc_id: str) -> None:
        """Launch a background thread to fetch full NPC graph data for the INSPECT tab."""
        threading.Thread(
            target=inspect_worker,
            args=(self._client, npc_id, self._inspect_q),
            daemon=True,
        ).start()

    def spawn_travel(self, location_id: str) -> None:
        """Launch a background thread to move the player to location_id."""
        threading.Thread(
            target=travel_worker,
            args=(self._client, self._player_id, location_id, self._travel_q),
            daemon=True,
        ).start()

    def spawn_bribe(self, npc_id: str) -> None:
        """Launch a background thread to bribe the selected NPC's faction.

        Looks up the faction from NPC_FACTIONS. No-op if the NPC has no faction entry.
        """
        faction_id = NPC_FACTIONS.get(npc_id)
        if not faction_id:
            if self._cb.on_set_status:
                self._cb.on_set_status(f"Cannot bribe: {npc_id} has no faction", 2.0)
            return
        threading.Thread(
            target=bribe_worker,
            args=(self._client, self._player_id, npc_id, faction_id, self._bribe_q),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Queue polling
    # ------------------------------------------------------------------

    def poll_sidebar_queue(self) -> None:
        """Drain one sidebar-fetch result and fire the appropriate callback."""
        try:
            status, npc_id, data = self._sidebar_fetch_q.get_nowait()
        except queue.Empty:
            return
        if status == "ok":
            display_name = LOCATION_DISPLAY_NAMES.get(npc_id, npc_id)
            if self._cb.on_sidebar_data:
                self._cb.on_sidebar_data(display_name, data)
        else:
            print(f"sidebar fetch error for {npc_id}: {data}", file=sys.stderr)
            if self._cb.on_clear_sidebar:
                self._cb.on_clear_sidebar()

    def poll_generate_quest_queue(self, right: RightPanelRenderer) -> None:
        """Drain one generate-quest result and switch to PLAYER STATUS tab."""
        try:
            status, payload = self._generate_quest_q.get_nowait()
        except queue.Empty:
            return
        if status == "ok":
            right.set_quest(payload)
            from demo_game.ui.right_panel import RightPanel as _RP
            right.switch_to(_RP.PLAYER_STATUS)
            if self._cb.on_set_status:
                self._cb.on_set_status("Quest generated!", 3.0)
        else:
            if self._cb.on_set_status:
                self._cb.on_set_status(f"Generate failed: {payload}", 3.0)

    def poll_inspect_queue(self, right: RightPanelRenderer) -> None:
        """Drain one inspect result and switch to INSPECT tab."""
        try:
            status, npc_id, payload = self._inspect_q.get_nowait()
        except queue.Empty:
            return
        if status == "ok":
            right.set_inspect_data(npc_id, payload)
            if self._cb.on_set_status:
                self._cb.on_set_status(f"Inspect: {npc_id}", 2.0)
        else:
            right.clear_inspect()
            if self._cb.on_set_status:
                self._cb.on_set_status(f"Inspect failed: {payload}", 2.0)

    def poll_travel_queue(self) -> None:
        """Drain one travel result and update status bar."""
        try:
            item = self._travel_q.get_nowait()
        except queue.Empty:
            return
        if item[0] == "ok" and self._cb.on_set_status:
            self._cb.on_set_status(f"Travelled to {item[1]}", 2.0)
        elif item[0] == "err" and self._cb.on_set_status:
            self._cb.on_set_status(f"Travel failed: {item[2]}", 2.0)

    def poll_bribe_queue(self) -> None:
        """Drain one bribe result and update status bar."""
        try:
            item = self._bribe_q.get_nowait()
        except queue.Empty:
            return
        if item[0] == "ok" and self._cb.on_set_status:
            faction_id, new_standing = item[1], item[2]
            self._cb.on_set_status(f"Bribed {faction_id}: standing now {new_standing}", 3.0)
        elif item[0] == "err" and self._cb.on_set_status:
            self._cb.on_set_status(f"Bribe failed: {item[2]}", 2.0)

    def poll_response_queue(self, active_npc_id: str, right: RightPanelRenderer) -> None:
        """Drain one dialogue result, update UI panels, and dispatch any proposal."""
        try:
            item = self._response_q.get_nowait()
        except queue.Empty:
            return

        self._is_waiting = False
        npc_id = self._pending_npc_id or active_npc_id

        if isinstance(item, (Exception, EngineClientError)):
            if self._cb.on_error:
                self._cb.on_error(npc_id, str(item))
            return

        turn: DialogueTurn = parse_dialogue_response(item)
        color = degradation_color(turn.degradation_level)
        if self._cb.on_npc_response:
            self._cb.on_npc_response(npc_id, turn, color)

        self._apply_relation_band(turn)
        if turn.interaction_proposal:
            self._dispatch_proposal(turn, npc_id, right)
        elif self._last_submitted_message == "I'd like to trade.":
            self._qt.open_trade_fallback(npc_id, right)

    # ------------------------------------------------------------------
    # Quest / trade / give-item — delegates to QuestTradeController
    # ------------------------------------------------------------------

    def on_quest_accept(self, right: RightPanelRenderer) -> None:
        """Accept the current active quest."""
        self._qt.on_quest_accept(right)

    def on_quest_complete(self, npc_id: str, right: RightPanelRenderer) -> None:
        """Send claim_completion for the current quest."""
        self._qt.on_quest_complete(npc_id, right)

    def on_quest_reward(self, right: RightPanelRenderer) -> None:
        """Apply quest rewards and refresh inventory."""
        self._qt.on_quest_reward(right)

    def on_trade_offer(self, npc_id: str, right: RightPanelRenderer) -> None:
        """Send the NPC's asking price as a currency offer."""
        self._qt.on_trade_offer(npc_id, right)

    def on_trade_confirm(self, npc_id: str, right: RightPanelRenderer) -> None:
        """Confirm a pending trade."""
        self._qt.on_trade_confirm(npc_id, right)

    def on_give_item(self, npc_id: str, item: dict | None, right: RightPanelRenderer) -> None:
        """Give the specified item to the NPC via the interaction endpoint."""
        self._qt.on_give_item(npc_id, item, right)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _apply_relation_band(self, turn: DialogueTurn) -> None:
        deltas = turn.relation_deltas
        if deltas.get("trust") or deltas.get("affection"):
            try:
                self._client.post_interaction_band(
                    player_id=self._player_id,
                    trust=deltas.get("trust", 0),
                    affection=deltas.get("affection", 0),
                )
            except EngineClientError:
                pass

    def _dispatch_proposal(self, turn: DialogueTurn, npc_id: str, right: RightPanelRenderer) -> None:
        from npc_engine.engines.interaction.models import InteractionProposal as _EngineProposal

        proposal = turn.interaction_proposal
        eng_proposal = _EngineProposal(
            kind=proposal.kind,
            target_id=proposal.target_id,
            payload=proposal.payload,
        )
        state = dispatch_interaction(eng_proposal)
        if self._cb.on_set_status:
            self._cb.on_set_status(f"[INTERACTION] {state.ui_directive}", 2.0)

        if proposal.kind == "propose_trade":
            self._qt.active_npc_id_for_trade = npc_id
            self._qt.open_trade(npc_id, proposal.payload, right)
        elif proposal.kind == "propose_quest":
            self._qt.open_quest(npc_id, proposal, right)
        elif proposal.kind in {"claim_completion", "give_item"}:
            self._qt.claim_completion(npc_id, proposal, right)
