"""
scenario_items_edge.py - Edge case coverage for Feature 3.6: Items and ownership.

Covers:
  - value=0 stored correctly (lower boundary)
  - is_unique=False serialized and stored correctly
  - character with no items returns empty list
  - ownership transfer: new owner has item, original does not
  - fetch after transfer reflects updated state
"""

from __future__ import annotations

import uuid

import httpx
import pytest

from e2e.scenarios.conftest import char_props

_ADMIN = "/v1/admin"
_GRAPH = "/v1/graph"


def _create_char(client: httpx.Client, char_id: str, name: str) -> None:
    resp = client.post(f"{_GRAPH}/nodes/Character", json={"properties": char_props(char_id, name, is_player=False)})
    assert resp.status_code == 200, f"Character creation failed: {resp.text}"


def _delete_char(client: httpx.Client, char_id: str) -> None:
    client.delete(f"{_ADMIN}/graph/characters/{char_id}")


def test_items_edge_cases(http_client: httpx.Client) -> None:
    suffix = uuid.uuid4().hex[:8]
    char_a = f"test_item_edge_a_{suffix}"
    char_b = f"test_item_edge_b_{suffix}"

    _create_char(http_client, char_a, "Item Edge A")
    _create_char(http_client, char_b, "Item Edge B")

    try:
        # --- Edge case 1: character with no items returns empty list ---
        resp = http_client.get(f"{_ADMIN}/items/{char_b}")
        assert resp.status_code == 200
        no_items = resp.json()["data"]["items"]
        assert no_items == [], f"Expected empty list for char_b, got {no_items}"
        print("[pass] character with no items returns empty list")

        # --- Edge case 2: value=0 (lower bound) stored correctly ---
        resp = http_client.post(
            f"{_ADMIN}/items/{char_a}",
            json={
                "name": "Worthless Trinket",
                "description": "Nobody wants this.",
                "value": 0,
                "rarity": "common",
                "type": "misc",
                "is_unique": False,
            },
        )
        assert resp.status_code == 200, resp.text
        id_worthless = resp.json()["data"]["item_id"]

        resp = http_client.get(f"{_ADMIN}/items/{char_a}")
        assert resp.status_code == 200
        char_a_items = resp.json()["data"]["items"]
        worthless = next(i for i in char_a_items if i["id"] == id_worthless)
        assert worthless["value"] == 0, f"value=0 not stored: got {worthless['value']}"
        print("[pass] value=0 stored correctly")

        # --- Edge case 3: is_unique=False stored correctly ---
        assert worthless["is_unique"] in ("false", False, 0), (
            f"is_unique=False not stored correctly: got {worthless['is_unique']!r}"
        )
        print("[pass] is_unique=False stored correctly")

        # --- Edge case 4: create a second item to transfer ---
        resp = http_client.post(
            f"{_ADMIN}/items/{char_a}",
            json={
                "name": "Steel Dagger",
                "description": "A sharp blade.",
                "value": 50,
                "rarity": "common",
                "type": "weapon",
                "is_unique": True,
            },
        )
        assert resp.status_code == 200, resp.text
        id_dagger = resp.json()["data"]["item_id"]

        # Verify char_a has 2 items before transfer
        resp = http_client.get(f"{_ADMIN}/items/{char_a}")
        before = resp.json()["data"]["items"]
        assert len(before) == 2, f"Expected 2 items before transfer, got {len(before)}"

        # --- Edge case 5: ownership transfer — char_b receives the dagger ---
        resp = http_client.patch(
            f"{_ADMIN}/items/{id_dagger}/owner",
            params={"from_character_id": char_a},
            json={"to_character_id": char_b},
        )
        assert resp.status_code == 200, resp.text

        resp_a = http_client.get(f"{_ADMIN}/items/{char_a}")
        resp_b = http_client.get(f"{_ADMIN}/items/{char_b}")
        after_a = resp_a.json()["data"]["items"]
        after_b = resp_b.json()["data"]["items"]

        assert len(after_a) == 1, f"char_a should have 1 item after transfer, got {len(after_a)}"
        assert after_a[0]["id"] == id_worthless, "char_a should still own the worthless trinket"
        assert len(after_b) == 1, f"char_b should have 1 item after transfer, got {len(after_b)}"
        assert after_b[0]["id"] == id_dagger, "char_b should now own the dagger"
        print("[pass] ownership transfer: char_b owns dagger, char_a still owns trinket")

        print("\n[PASS] scenario_items_edge completed successfully.")

    finally:
        _delete_char(http_client, char_a)
        _delete_char(http_client, char_b)
