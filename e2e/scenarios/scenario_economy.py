"""
scenario_economy.py - Economy engine: pricing and trade offer evaluation (Phase 4.4).

Scenario:
  1. Seed buyer (with currency_balance=100), seller, and a location node.
  2. Place seller AT the location via an AT edge.
  3. Give seller an item (sword) via POST /v1/admin/items/{seller_id}.
  4. Call GET /v1/admin/economy/price — record the fair price for a sword at the seller's location.
  5. Call POST /v1/admin/economy/trade with offered_price = fair_price — assert accepted=True.
  6. Assert buyer now owns the item (GET /v1/admin/items/{buyer_id}).
  7. Cleanup all seeded nodes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx

from e2e.scenarios.conftest import Narrator, api_get, api_post, char_props, loc_props

SCENARIO_ID = "scenario_economy"
_GRAPH = "/v1/graph"
_ADMIN = "/v1/admin"


def test_economy_trade(http_client: httpx.Client) -> None:
    n = Narrator(SCENARIO_ID)
    suffix = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()

    buyer_id = f"eco_buyer_{suffix}"
    seller_id = f"eco_seller_{suffix}"
    location_id = f"eco_location_{suffix}"
    item_type = "sword"

    try:
        n.narrate("Seed buyer, seller, and a frontier location for the trade scenario.")

        buyer_props = char_props(buyer_id, "Economy Buyer", is_player=True, now=now)
        buyer_props = {**buyer_props, "currency_balance": 100}

        n.step("Create buyer with 100 currency", api_post(http_client, f"{_GRAPH}/nodes/Character", {
            "properties": buyer_props,
        }))

        n.step("Create seller", api_post(http_client, f"{_GRAPH}/nodes/Character", {
            "properties": char_props(seller_id, "Economy Seller", is_player=False, now=now),
        }))

        n.step("Create frontier location", api_post(http_client, f"{_GRAPH}/nodes/Location", {
            "properties": {
                **loc_props(location_id, "Economy Test Frontier", location_tag="frontier", now=now),
                "location_type": "frontier",
            },
        }))

        n.narrate("Place seller at the frontier location so pricing queries can resolve location context.")

        n.step("Place seller AT location", api_post(http_client, f"{_GRAPH}/edges/AT", {
            "src_id": seller_id,
            "dst_id": location_id,
            "properties": {"since": now},
        }))

        n.narrate("Give the seller a sword item.")

        item_resp = api_post(http_client, f"{_ADMIN}/items/{seller_id}", {
            "name": "Iron Sword",
            "description": "A sturdy iron sword.",
            "value": 50,
            "rarity": "common",
            "type": item_type,
            "is_unique": True,
            "game_time": {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"},
        })
        n.step("Create sword item for seller", item_resp)
        item_id = item_resp["body"].get("data", {}).get("item_id", "")
        assert item_id, f"Expected item_id in response; got {item_resp['body']}"

        n.narrate("Query the economy API for the fair price of a sword at the seller's location.")

        price_resp = http_client.get(
            f"{_ADMIN}/economy/price",
            params={"item_type": item_type, "character_id": seller_id},
        )
        assert price_resp.status_code == 200, f"Price query failed: {price_resp.text}"
        fair_price = price_resp.json()["data"]["price"]
        n.step("Get fair price", {"url": str(price_resp.url), "status": price_resp.status_code, "body": price_resp.json()})
        assert isinstance(fair_price, int) and fair_price > 0, f"Expected positive int fair_price; got {fair_price}"

        n.narrate(f"Offer fair_price={fair_price} — the trade engine should accept.")

        trade_resp = api_post(http_client, f"{_ADMIN}/economy/trade", {
            "buyer_id": buyer_id,
            "seller_id": seller_id,
            "item_id": item_id,
            "item_type": item_type,
            "offered_price": fair_price,
            "current_tick": 0,
        })
        n.step("Execute trade at fair price", trade_resp)

        trade_data = trade_resp["body"].get("data", {})
        assert trade_data.get("accepted") is True, (
            f"Expected trade to be accepted; got accepted={trade_data.get('accepted')}, "
            f"reason={trade_data.get('rejection_reason')}"
        )
        assert trade_data.get("final_price") == fair_price, (
            f"Expected final_price == fair_price ({fair_price}); got {trade_data.get('final_price')}"
        )

        n.narrate("Verify buyer now owns the sword.")

        items_resp = api_get(http_client, f"{_ADMIN}/items/{buyer_id}")
        n.step("List buyer items", items_resp)
        buyer_items = items_resp["body"].get("data", {}).get("items", [])
        buyer_item_ids = [it.get("id", "") for it in buyer_items]
        assert item_id in buyer_item_ids, (
            f"Expected buyer to own item {item_id}; buyer items: {buyer_item_ids}"
        )

    finally:
        http_client.delete(f"{_ADMIN}/graph/characters/{buyer_id}")
        http_client.delete(f"{_ADMIN}/graph/characters/{seller_id}")
        http_client.delete(f"{_GRAPH}/nodes/Location/{location_id}")
        n.save()
