"""
scenario_items.py - E2E scenario for Feature 3.6: Item nodes and ownership.

Requires: running NPC Engine API server (make run).
Run with: python e2e/scenarios/scenario_items.py

Steps:
  1. Create two Character nodes via the HTTP API.
  2. Create an item owned by character 1.
  3. Fetch items for character 1 and assert one returned.
  4. Transfer ownership to character 2.
  5. Fetch items for character 1 and assert empty.
  6. Fetch items for character 2 and assert one returned.
  7. Cleanup.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

import httpx

_BASE = os.getenv("NPC_BASE_URL", "http://localhost:8000")
_KEY = os.getenv("NPC_API_KEY", "local_dev_secret_change_this_2026")
_ADMIN = "/v1/admin"
_GRAPH = "/v1/graph"

_CHAR1_ID = f"e2e_item_char1_{uuid.uuid4().hex[:8]}"
_CHAR2_ID = f"e2e_item_char2_{uuid.uuid4().hex[:8]}"


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=_BASE,
        headers={"Authorization": f"Bearer {_KEY}"},
        timeout=30.0,
    )


def _char_props(char_id: str, name: str) -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "id": char_id,
        "name": name,
        "archetype": "adventurer",
        "biography": "A test character.",
        "is_player": False,
        "is_active": True,
        "created_at": ts,
        "updated_at": ts,
        "last_graph_updated_at": ts,
        "gossipy": 50,
        "credulity": 50,
        "honesty": 50,
    }


def run() -> None:
    with _client() as client:
        # Step 1: create two characters
        for char_id, name in [(_CHAR1_ID, "E2E NPC One"), (_CHAR2_ID, "E2E NPC Two")]:
            resp = client.post(
                f"{_GRAPH}/nodes/Character",
                json={"properties": _char_props(char_id, name)},
            )
            assert resp.status_code == 200, f"Character {name} creation failed: {resp.text}"
        print(f"[seed] Characters {_CHAR1_ID} and {_CHAR2_ID} created.")

        item_id = None
        try:
            # Step 2: create item owned by character 1
            resp = client.post(
                f"{_ADMIN}/items/{_CHAR1_ID}",
                json={
                    "name": "Ancient Compass",
                    "description": "Points toward hidden treasure.",
                    "value": 200,
                    "rarity": "rare",
                    "type": "misc",
                    "is_unique": True,
                },
            )
            assert resp.status_code == 200, resp.text
            item_id = resp.json()["data"]["item_id"]
            print(f"[create] Item {item_id} created and assigned to {_CHAR1_ID}.")

            # Step 3: fetch items for character 1 — expect one
            resp = client.get(f"{_ADMIN}/items/{_CHAR1_ID}")
            assert resp.status_code == 200
            items_1 = resp.json()["data"]["items"]
            assert len(items_1) == 1, f"Expected 1 item for char1, got {len(items_1)}"
            assert items_1[0]["name"] == "Ancient Compass"
            print("[assert] Character 1 owns 1 item. OK.")

            # Step 4: transfer ownership to character 2
            resp = client.patch(
                f"{_ADMIN}/items/{item_id}/owner",
                params={"from_character_id": _CHAR1_ID},
                json={"to_character_id": _CHAR2_ID},
            )
            assert resp.status_code == 200, resp.text
            print(f"[transfer] Item {item_id} transferred to {_CHAR2_ID}.")

            # Step 5: fetch items for character 1 — expect empty
            resp = client.get(f"{_ADMIN}/items/{_CHAR1_ID}")
            items_1_after = resp.json()["data"]["items"]
            assert len(items_1_after) == 0, (
                f"Expected 0 items for char1 after transfer, got {len(items_1_after)}"
            )
            print("[assert] Character 1 owns 0 items after transfer. OK.")

            # Step 6: fetch items for character 2 — expect one
            resp = client.get(f"{_ADMIN}/items/{_CHAR2_ID}")
            items_2 = resp.json()["data"]["items"]
            assert len(items_2) == 1, f"Expected 1 item for char2, got {len(items_2)}"
            assert items_2[0]["name"] == "Ancient Compass"
            print("[assert] Character 2 owns 1 item. OK.")

            print("\n[PASS] scenario_items completed successfully.")

        finally:
            if item_id:
                client.delete(f"{_ADMIN}/items/{item_id}")
            client.delete(f"{_ADMIN}/graph/characters/{_CHAR1_ID}")
            client.delete(f"{_ADMIN}/graph/characters/{_CHAR2_ID}")
            print("[cleanup] Nodes removed.")


if __name__ == "__main__":
    run()
