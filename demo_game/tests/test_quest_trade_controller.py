"""
Module: test_quest_trade_controller
Layer: demo_game (tests)
Purpose: Unit tests for QuestTradeController — give_item handler and on_give_item
         response routing. No pygame, no network, all I/O mocked.
Dependencies: demo_game.quest_trade_controller, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(interaction_response: dict | None = None, items: list | None = None) -> MagicMock:
    client = MagicMock()
    if interaction_response is not None:
        client.post_interaction.return_value = interaction_response
    if items is not None:
        client.get_items_for_character.return_value = items
        client.get_node.return_value = {"currency_balance": 100}
    return client


def _make_right() -> MagicMock:
    right = MagicMock()
    right.get_trade_state.return_value = None
    return right


def _make_controller(client=None, statuses=None):
    from demo_game.quest_trade_controller import QuestTradeController

    captured = statuses if statuses is not None else []
    client = client or _make_client()
    ctrl = QuestTradeController(
        client=client,
        player_id="hero_player",
        on_set_status=lambda text, dur: captured.append(text),
    )
    return ctrl, captured


# ---------------------------------------------------------------------------
# on_give_item — no item in inventory
# ---------------------------------------------------------------------------


def test_give_item_no_item_shows_status() -> None:
    ctrl, statuses = _make_controller()
    ctrl.on_give_item("mira_innkeeper", None, _make_right())
    assert any("No items" in s for s in statuses)


def test_give_item_no_item_does_not_call_api() -> None:
    client = _make_client()
    ctrl, _ = _make_controller(client)
    ctrl.on_give_item("mira_innkeeper", None, _make_right())
    client.post_interaction.assert_not_called()


# ---------------------------------------------------------------------------
# on_give_item — non-quest gift (open/none response)
# ---------------------------------------------------------------------------


def test_give_item_open_shows_gave_status() -> None:
    client = _make_client(
        interaction_response={"data": {"status": "open", "ui_directive": "none"}},
        items=[],
    )
    ctrl, statuses = _make_controller(client)
    item = {"id": "spice_bundle_01", "name": "Spice Bundle"}
    ctrl.on_give_item("aldric_merchant", item, _make_right())
    assert any("Spice Bundle" in s and "aldric_merchant" in s for s in statuses)


def test_give_item_calls_post_interaction_with_correct_kind() -> None:
    client = _make_client(
        interaction_response={"data": {"status": "open", "ui_directive": "none"}},
        items=[],
    )
    ctrl, _ = _make_controller(client)
    item = {"id": "sword_01", "name": "Sword"}
    ctrl.on_give_item("captain_sorn", item, _make_right())
    call_kwargs = client.post_interaction.call_args
    assert call_kwargs is not None
    proposal = call_kwargs.kwargs.get("proposal") or call_kwargs[1].get("proposal") or {}
    assert proposal.get("kind") == "give_item"
    assert proposal.get("target_id") == "sword_01"


# ---------------------------------------------------------------------------
# on_give_item — quest-intercept response (show_quest_panel)
# ---------------------------------------------------------------------------


def test_give_item_quest_intercept_switches_to_player_status() -> None:
    client = _make_client(
        interaction_response={
            "data": {
                "status": "pending_confirm",
                "ui_directive": "show_quest_panel",
                "negotiation_state": {"quest_id": "q_deliver_01"},
            }
        },
        items=[],
    )
    ctrl, statuses = _make_controller(client)
    item = {"id": "relic_01", "name": "Relic"}
    right = _make_right()
    ctrl.on_give_item("lira_fence", item, right)
    right.set_quest.assert_called_once_with({"quest_id": "q_deliver_01"})
    right.switch_to.assert_called_once()


def test_give_item_quest_intercept_shows_delivered_status() -> None:
    client = _make_client(
        interaction_response={
            "data": {
                "status": "pending_confirm",
                "ui_directive": "show_quest_panel",
                "negotiation_state": {"quest_id": "q_deliver_01"},
            }
        },
        items=[],
    )
    ctrl, statuses = _make_controller(client)
    item = {"id": "relic_01", "name": "Relic"}
    ctrl.on_give_item("lira_fence", item, _make_right())
    assert any("delivered" in s.lower() for s in statuses)


# ---------------------------------------------------------------------------
# on_give_item — API error
# ---------------------------------------------------------------------------


def test_give_item_api_error_shows_error_status() -> None:
    from demo_game.client import EngineClientError

    client = MagicMock()
    client.post_interaction.side_effect = EngineClientError("500 Internal Server Error")
    ctrl, statuses = _make_controller(client)
    item = {"id": "coin_01", "name": "Gold Coin"}
    ctrl.on_give_item("old_henryk", item, _make_right())
    assert any("give_item error" in s for s in statuses)


# ---------------------------------------------------------------------------
# on_give_item — inventory refreshed after successful call
# ---------------------------------------------------------------------------


def test_give_item_refreshes_inventory_after_open_response() -> None:
    client = _make_client(
        interaction_response={"data": {"status": "open", "ui_directive": "none"}},
        items=[{"id": "pouch_01", "name": "Coin Pouch"}],
    )
    ctrl, _ = _make_controller(client)
    item = {"id": "spice_01", "name": "Spice"}
    right = _make_right()
    ctrl.on_give_item("mira_innkeeper", item, right)
    right.set_inventory.assert_called_once()
