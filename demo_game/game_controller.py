"""
Module: game_controller
Layer: demo_game
Purpose: Background-thread orchestration, response-queue dispatch, and quest/trade
         action handlers for the demo game. Decoupled from pygame rendering so it
         can be unit-tested without a display.
Dependencies: demo_game.client, demo_game.config, demo_game.dialogue,
              demo_game.knowledge_sidebar_fetcher,
              npc_engine.engines.interaction
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import queue
import sys
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from demo_game.client import EngineClient, EngineClientError
from demo_game.constants import LOCATION_DISPLAY_NAMES
from demo_game.dialogue import build_dialogue_payload, degradation_color, parse_dialogue_response, DialogueTurn
from demo_game.knowledge_sidebar_fetcher import fetch_npc_knowledge
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


def _dialogue_worker(client: EngineClient, payload: dict, result_q: queue.Queue) -> None:
    """Call post_dialogue in a daemon thread and push the result or exception."""
    try:
        result_q.put(client.post_dialogue(**payload))
    except Exception as exc:
        result_q.put(exc)


def _fetch_sidebar_worker(client: EngineClient, npc_id: str, result_q: queue.Queue) -> None:
    """Fetch KNOWS_ABOUT pairs for npc_id and push (status, npc_id, data)."""
    try:
        pairs = fetch_npc_knowledge(client, npc_id)
        result_q.put(("ok", npc_id, pairs))
    except Exception as exc:
        result_q.put(("err", npc_id, exc))


class GameController:
    """Manages background threads, queues, and interaction dispatch for the demo.

    Also owns quest/trade callbacks so GameWindow stays under 300 lines.

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
        self._is_waiting = False
        self._pending_npc_id: str | None = None
        self._last_submitted_message: str = ""
        self.quest_id: str | None = None
        self.active_npc_id_for_trade: str | None = None

    @property
    def is_waiting(self) -> bool:
        """True while a dialogue request is in-flight."""
        return self._is_waiting

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
            target=_dialogue_worker,
            args=(self._client, payload, self._response_q),
            daemon=True,
        ).start()

    def spawn_sidebar_fetch(self, npc_id: str) -> None:
        """Launch a background thread to fetch KNOWS_ABOUT data for npc_id."""
        threading.Thread(
            target=_fetch_sidebar_worker,
            args=(self._client, npc_id, self._sidebar_fetch_q),
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
            self._open_trade_fallback(npc_id, right)

    # ------------------------------------------------------------------
    # Quest / trade action handlers (owned here to keep GameWindow thin)
    # ------------------------------------------------------------------

    def on_quest_accept(self, right: RightPanelRenderer) -> None:
        """Accept the current active quest."""
        if not self.quest_id:
            return
        try:
            self._client.post_quest_accept(self.quest_id, self._player_id)
        except EngineClientError:
            return
        right.set_quest(self._client.get_quest(self.quest_id))

    def on_quest_complete(self, npc_id: str, right: RightPanelRenderer) -> None:
        """Send claim_completion for the current quest."""
        if not self.quest_id:
            return
        try:
            result = self._client.post_interaction(
                player_id=self._player_id,
                npc_id=npc_id,
                proposal={"kind": "claim_completion", "target_id": self.quest_id, "payload": {}},
            )
        except EngineClientError as exc:
            if self._cb.on_set_status:
                self._cb.on_set_status(f"claim error: {exc}", 2.0)
            return
        data = result.get("data") or {}
        if data.get("negotiation_state"):
            right.set_quest(data["negotiation_state"])
        if data.get("status") == "pending_confirm":
            from demo_game.ui.right_panel import RightPanel as _RP
            right.switch_to(_RP.PLAYER_STATUS)
            if self._cb.on_set_status:
                self._cb.on_set_status("Quest complete — accept reward above", 2.0)
        elif data.get("narration_hint") == "npc_refuses_objective_not_met":
            if self._cb.on_set_status:
                self._cb.on_set_status("Objectives not yet met", 2.0)

    def on_quest_reward(self, right: RightPanelRenderer) -> None:
        """Apply quest rewards and refresh inventory."""
        if not self.quest_id:
            return
        try:
            result = self._client.post_quest_reward(self.quest_id, self._player_id)
        except EngineClientError as exc:
            if self._cb.on_set_status:
                self._cb.on_set_status(f"reward error: {exc}", 2.0)
            return
        quest_state = result.get("data", {}).get("quest_state") if isinstance(result.get("data"), dict) else None
        if quest_state:
            right.set_quest(quest_state)
        if self._cb.on_set_status:
            self._cb.on_set_status("Rewards applied!", 2.0)
        self._refresh_inventory(right)

    def on_trade_offer(self, npc_id: str, right: RightPanelRenderer) -> None:
        """Send the NPC's asking price as a currency offer."""
        try:
            result = self._client.post_interaction(
                player_id=self._player_id,
                npc_id=npc_id,
                proposal={"kind": "currency_offer_asking", "target_id": None, "payload": {}},
            )
            right.set_negotiation_state((result.get("data") or {}).get("negotiation_state"))
        except EngineClientError as exc:
            if self._cb.on_set_status:
                self._cb.on_set_status(f"offer error: {exc}", 2.0)

    def on_trade_confirm(self, npc_id: str, right: RightPanelRenderer) -> None:
        """Confirm a pending trade: execute item+currency transfer."""
        state = right.get_trade_state()
        if not state or state.get("status") != "pending_confirm":
            return
        offered_price = state.get("current_offer") or state.get("threshold", 0)
        try:
            self._client.post_trade(
                buyer_id=self._player_id,
                seller_id=npc_id,
                item_id=state["item_id"],
                item_type=state.get("item_type", "spice"),
                offered_price=int(offered_price),
                tick=0,
            )
        except EngineClientError as exc:
            if self._cb.on_set_status:
                self._cb.on_set_status(f"trade failed: {exc}", 2.0)
            return
        right.set_negotiation_state(None)
        if self._cb.on_set_status:
            self._cb.on_set_status("Trade complete!", 4.0)
        try:
            from demo_game.ui.right_panel import RightPanel as _RP
            self._refresh_inventory(right)
            right.switch_to(_RP.PLAYER_INVENTORY)
        except EngineClientError:
            pass

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _refresh_inventory(self, right: RightPanelRenderer) -> None:
        try:
            right.set_inventory(self._client.get_items_for_character(self._player_id))
            char = self._client.get_node("Character", self._player_id)
            right.set_player_gold((char or {}).get("currency_balance"))
        except EngineClientError:
            pass

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
            self.active_npc_id_for_trade = npc_id
            self._open_trade(npc_id, proposal.payload, right)
        elif proposal.kind == "propose_quest":
            self._open_quest(npc_id, proposal, right)
        elif proposal.kind in {"claim_completion", "give_item"}:
            self._claim_completion(npc_id, proposal, right)

    def _open_trade(self, npc_id: str, payload: dict, right: RightPanelRenderer) -> None:
        from demo_game.ui.right_panel import RightPanel as _RP

        try:
            npc_char = self._client.get_node("Character", npc_id)
            right.set_npc_trade_gold((npc_char or {}).get("currency_balance"))
        except EngineClientError:
            pass
        try:
            result = self._client.post_interaction(
                player_id=self._player_id,
                npc_id=npc_id,
                proposal={"kind": "propose_trade", "target_id": "northern_spice_bundle", "payload": payload},
            )
            right.set_negotiation_state((result.get("data") or {}).get("negotiation_state"))
            right.switch_to(_RP.TRADE)
        except EngineClientError as exc:
            if self._cb.on_set_status:
                self._cb.on_set_status(f"trade open error: {exc}", 2.0)

    def _open_quest(self, npc_id: str, proposal: Any, right: RightPanelRenderer) -> None:
        from demo_game.ui.right_panel import RightPanel as _RP

        try:
            result = self._client.post_interaction(
                player_id=self._player_id,
                npc_id=npc_id,
                proposal={"kind": "propose_quest", "target_id": proposal.target_id, "payload": proposal.payload},
            )
            quest_state = (result.get("data") or {}).get("negotiation_state")
            if quest_state:
                right.set_quest(quest_state)
                self.quest_id = quest_state.get("quest_id") or self.quest_id
            right.switch_to(_RP.PLAYER_STATUS)
        except EngineClientError as exc:
            if self._cb.on_set_status:
                self._cb.on_set_status(f"quest open error: {exc}", 2.0)

    def _claim_completion(self, npc_id: str, proposal: Any, right: RightPanelRenderer) -> None:
        from demo_game.ui.right_panel import RightPanel as _RP

        try:
            result = self._client.post_interaction(
                player_id=self._player_id,
                npc_id=npc_id,
                proposal={"kind": proposal.kind, "target_id": proposal.target_id, "payload": proposal.payload},
            )
            data = result.get("data") or {}
            if data.get("negotiation_state"):
                right.set_quest(data["negotiation_state"])
            if data.get("status") == "pending_confirm":
                right.switch_to(_RP.PLAYER_STATUS)
                if self._cb.on_set_status:
                    self._cb.on_set_status("Quest complete — accept reward above", 2.0)
        except EngineClientError as exc:
            if self._cb.on_set_status:
                self._cb.on_set_status(f"claim error: {exc}", 2.0)

    def _open_trade_fallback(self, npc_id: str, right: RightPanelRenderer) -> None:
        from demo_game.ui.right_panel import RightPanel as _RP

        self.active_npc_id_for_trade = npc_id
        try:
            npc_char = self._client.get_node("Character", npc_id)
            right.set_npc_trade_gold((npc_char or {}).get("currency_balance"))
        except EngineClientError:
            pass
        try:
            result = self._client.post_interaction(
                player_id=self._player_id,
                npc_id=npc_id,
                proposal={"kind": "propose_trade", "target_id": "northern_spice_bundle", "payload": {"item_type": "spice"}},
            )
            right.set_negotiation_state((result.get("data") or {}).get("negotiation_state"))
            right.switch_to(_RP.TRADE)
        except EngineClientError as exc:
            if self._cb.on_set_status:
                self._cb.on_set_status(f"trade fallback error: {exc}", 2.0)
