"""
Module: quest_trade_controller
Layer: demo_game
Purpose: Synchronous quest, trade, and give-item action handlers for the demo.
         Each method executes one or more API calls on the calling thread (main pygame
         thread) and updates the right panel directly. Extracted from game_controller.py
         to keep that file under the 300-line limit (ISSUE-048).
Dependencies: demo_game.client
Used by: demo_game.game_controller
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Callable

from demo_game.client import EngineClient, EngineClientError

if TYPE_CHECKING:
    from demo_game.ui.right_panel import RightPanelRenderer

_HINT_QUEST_COMPLETE = "Quest complete — accept reward above"
_HINT_OBJECTIVES_NOT_MET = "Objectives not yet met"


class QuestTradeController:
    """Synchronous quest, trade, and give-item action handlers.

    All methods block on HTTP calls and must be called from the main pygame thread.
    They update the right panel immediately after the call completes.

    Args:
        client: Initialised EngineClient.
        player_id: Player character ID.
        on_set_status: Callback ``(text, duration_s)`` for the status overlay.
    """

    def __init__(
        self,
        client: EngineClient,
        player_id: str,
        on_set_status: Callable[[str, float], None] | None = None,
    ) -> None:
        self._client = client
        self._player_id = player_id
        self._on_set_status = on_set_status
        self.quest_id: str | None = None
        self.active_npc_id_for_trade: str | None = None

    # ------------------------------------------------------------------
    # Quest handlers
    # ------------------------------------------------------------------

    def on_quest_accept(self, right: RightPanelRenderer) -> None:
        """Accept the current active quest via the lifecycle engine."""
        if not self.quest_id:
            return
        try:
            self._client.post_quest_accept(self.quest_id, self._player_id)
        except EngineClientError:
            return
        right.set_quest(self._client.get_quest(self.quest_id))

    def on_quest_complete(self, npc_id: str, right: RightPanelRenderer) -> None:
        """Send claim_completion for the current quest and handle the response."""
        if not self.quest_id:
            return
        try:
            result = self._client.post_interaction(
                player_id=self._player_id,
                npc_id=npc_id,
                proposal={"kind": "claim_completion", "target_id": self.quest_id, "payload": {}},
            )
        except EngineClientError as exc:
            self._status(f"claim error: {exc}", 2.0)
            return
        data = result.get("data") or {}
        if data.get("negotiation_state"):
            right.set_quest(data["negotiation_state"])
        if data.get("status") == "pending_confirm":
            from demo_game.ui.right_panel import RightPanel as _RP
            right.switch_to(_RP.PLAYER_STATUS)
            self._status(_HINT_QUEST_COMPLETE, 2.0)
        elif data.get("narration_hint") == "npc_refuses_objective_not_met":
            self._status(_HINT_OBJECTIVES_NOT_MET, 2.0)

    def on_quest_reward(self, right: RightPanelRenderer) -> None:
        """Apply quest rewards and refresh the player inventory."""
        if not self.quest_id:
            return
        try:
            result = self._client.post_quest_reward(self.quest_id, self._player_id)
        except EngineClientError as exc:
            self._status(f"reward error: {exc}", 2.0)
            return
        quest_state = (
            result.get("data", {}).get("quest_state")
            if isinstance(result.get("data"), dict)
            else None
        )
        if quest_state:
            right.set_quest(quest_state)
        self._status("Rewards applied!", 2.0)
        self._refresh_inventory(right)

    # ------------------------------------------------------------------
    # Trade handlers
    # ------------------------------------------------------------------

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
            self._status(f"offer error: {exc}", 2.0)

    def on_trade_confirm(self, npc_id: str, right: RightPanelRenderer) -> None:
        """Confirm a pending trade: execute item + currency transfer."""
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
            self._status(f"trade failed: {exc}", 2.0)
            return
        right.set_negotiation_state(None)
        self._status("Trade complete!", 4.0)
        try:
            from demo_game.ui.right_panel import RightPanel as _RP
            self._refresh_inventory(right)
            right.switch_to(_RP.PLAYER_INVENTORY)
        except EngineClientError as exc:
            print(f"[quest_trade_controller] inventory refresh failed: {exc}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Give-item handler
    # ------------------------------------------------------------------

    def on_give_item(self, npc_id: str, item: dict | None, right: RightPanelRenderer) -> None:
        """Give the specified item to an NPC via the interaction endpoint.

        If no item is provided (empty inventory), shows a status message and
        returns early. If the item matches an active quest deliver objective the
        server intercepts it as a quest completion (show_quest_panel / show_reward_overlay).
        Otherwise shows a gift-delivered status.

        Args:
            npc_id: Recipient NPC character ID.
            item: Item property dict from the player's inventory, or None.
            right: Right panel renderer to update after the call.
        """
        if not item:
            self._status("No items to give", 2.0)
            return
        item_id = item.get("id") or ""
        item_name = item.get("name") or item_id
        try:
            result = self._client.post_interaction(
                player_id=self._player_id,
                npc_id=npc_id,
                proposal={"kind": "give_item", "target_id": item_id, "payload": {"item_id": item_id}},
            )
        except EngineClientError as exc:
            self._status(f"give_item error: {exc}", 2.0)
            return
        data = result.get("data") or {}
        ui_directive = data.get("ui_directive") or ""
        if ui_directive in {"show_quest_panel", "show_reward_overlay"}:
            if data.get("negotiation_state"):
                right.set_quest(data["negotiation_state"])
            from demo_game.ui.right_panel import RightPanel as _RP
            right.switch_to(_RP.PLAYER_STATUS)
            self._status(f"Gave {item_name} — quest delivered!", 3.0)
        else:
            self._status(f"Gave {item_name} to {npc_id}", 2.0)
        self._refresh_inventory(right)

    # ------------------------------------------------------------------
    # Proposal-dispatch helpers (called from GameController._dispatch_proposal)
    # ------------------------------------------------------------------

    def open_trade(self, npc_id: str, payload: dict, right: RightPanelRenderer) -> None:
        """Open or resume a trade session for the given NPC."""
        from demo_game.ui.right_panel import RightPanel as _RP
        try:
            npc_char = self._client.get_node("Character", npc_id)
            right.set_npc_trade_gold((npc_char or {}).get("currency_balance"))
        except EngineClientError as exc:
            print(f"[quest_trade_controller] npc gold fetch failed: {exc}", file=sys.stderr)
        try:
            result = self._client.post_interaction(
                player_id=self._player_id,
                npc_id=npc_id,
                proposal={"kind": "propose_trade", "target_id": "northern_spice_bundle", "payload": payload},
            )
            right.set_negotiation_state((result.get("data") or {}).get("negotiation_state"))
            right.switch_to(_RP.TRADE)
        except EngineClientError as exc:
            self._status(f"trade open error: {exc}", 2.0)

    def open_quest(self, npc_id: str, proposal: Any, right: RightPanelRenderer) -> None:
        """Open a quest proposal session for the given NPC."""
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
            self._status(f"quest open error: {exc}", 2.0)

    def claim_completion(self, npc_id: str, proposal: Any, right: RightPanelRenderer) -> None:
        """Send a claim_completion or give_item proposal and handle the response."""
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
                self._status(_HINT_QUEST_COMPLETE, 2.0)
        except EngineClientError as exc:
            self._status(f"claim error: {exc}", 2.0)

    def open_trade_fallback(self, npc_id: str, right: RightPanelRenderer) -> None:
        """Open a trade session via the fallback path (player typed 'I'd like to trade.')."""
        from demo_game.ui.right_panel import RightPanel as _RP
        self.active_npc_id_for_trade = npc_id
        try:
            npc_char = self._client.get_node("Character", npc_id)
            right.set_npc_trade_gold((npc_char or {}).get("currency_balance"))
        except EngineClientError as exc:
            print(f"[quest_trade_controller] npc gold fetch failed: {exc}", file=sys.stderr)
        try:
            result = self._client.post_interaction(
                player_id=self._player_id,
                npc_id=npc_id,
                proposal={"kind": "propose_trade", "target_id": "northern_spice_bundle", "payload": {"item_type": "spice"}},
            )
            right.set_negotiation_state((result.get("data") or {}).get("negotiation_state"))
            right.switch_to(_RP.TRADE)
        except EngineClientError as exc:
            self._status(f"trade fallback error: {exc}", 2.0)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _refresh_inventory(self, right: RightPanelRenderer) -> None:
        try:
            right.set_inventory(self._client.get_items_for_character(self._player_id))
            char = self._client.get_node("Character", self._player_id)
            right.set_player_gold((char or {}).get("currency_balance"))
        except EngineClientError as exc:
            print(f"[quest_trade_controller] inventory/gold refresh failed: {exc}", file=sys.stderr)

    def _status(self, text: str, duration: float = 2.0) -> None:
        if self._on_set_status is not None:
            self._on_set_status(text, duration)
