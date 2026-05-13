"""
scenario_beliefs_edge.py - Edge case coverage for Feature 3.4: Belief nodes.

Covers:
  - confidence=0 and confidence=100 stored correctly (boundary values)
  - beliefs sorted descending by confidence
  - k=0 returns empty list; k>total returns all without error
  - character with no beliefs returns empty list
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


def test_beliefs_edge_cases(http_client: httpx.Client) -> None:
    suffix = uuid.uuid4().hex[:8]
    char_a = f"test_belief_edge_a_{suffix}"
    char_b = f"test_belief_edge_b_{suffix}"

    _create_char(http_client, char_a, "Edge A")
    _create_char(http_client, char_b, "Edge B")

    try:
        # --- Edge case 1: confidence=0 (lower bound) stored correctly ---
        resp = http_client.post(
            f"{_ADMIN}/beliefs/{char_a}",
            json={"content": "Absolute uncertainty.", "confidence": 0},
        )
        assert resp.status_code == 200, resp.text
        id_low = resp.json()["data"]["belief_id"]

        resp = http_client.get(f"{_ADMIN}/beliefs/{char_a}", params={"k": 10})
        assert resp.status_code == 200
        beliefs = resp.json()["data"]["beliefs"]

        low_belief = next(b for b in beliefs if b["id"] == id_low)
        assert low_belief["confidence"] == 0, f"confidence=0 not stored: got {low_belief['confidence']}"
        print("[pass] confidence=0 stored correctly")

        # --- Edge case 2: confidence=100 (upper bound) stored correctly ---
        resp = http_client.post(
            f"{_ADMIN}/beliefs/{char_a}",
            json={"content": "Absolute certainty.", "confidence": 100},
        )
        assert resp.status_code == 200, resp.text
        id_high = resp.json()["data"]["belief_id"]

        resp = http_client.get(f"{_ADMIN}/beliefs/{char_a}", params={"k": 10})
        assert resp.status_code == 200
        beliefs = resp.json()["data"]["beliefs"]

        high_belief = next(b for b in beliefs if b["id"] == id_high)
        assert high_belief["confidence"] == 100, f"confidence=100 not stored: got {high_belief['confidence']}"
        print("[pass] confidence=100 stored correctly")

        # --- Edge case 3: sorted descending by confidence ---
        assert beliefs[0]["confidence"] >= beliefs[1]["confidence"], (
            f"Expected descending order, got {[b['confidence'] for b in beliefs]}"
        )
        print("[pass] beliefs sorted descending by confidence")

        # --- Edge case 4: k=0 returns empty list ---
        resp = http_client.get(f"{_ADMIN}/beliefs/{char_a}", params={"k": 0})
        assert resp.status_code == 200
        empty = resp.json()["data"]["beliefs"]
        assert empty == [], f"k=0 should return empty list, got {empty}"
        print("[pass] k=0 returns empty list")

        # --- Edge case 5: k > total returns all (no error, no truncation) ---
        resp = http_client.get(f"{_ADMIN}/beliefs/{char_a}", params={"k": 1000})
        assert resp.status_code == 200
        all_beliefs = resp.json()["data"]["beliefs"]
        assert len(all_beliefs) == 2, f"k=1000 with 2 beliefs should return 2, got {len(all_beliefs)}"
        print("[pass] k=1000 returns all available beliefs without error")

        # --- Edge case 6: character with no beliefs returns empty list ---
        resp = http_client.get(f"{_ADMIN}/beliefs/{char_b}", params={"k": 5})
        assert resp.status_code == 200
        none_beliefs = resp.json()["data"]["beliefs"]
        assert none_beliefs == [], f"Character with no beliefs should return [], got {none_beliefs}"
        print("[pass] character with no beliefs returns empty list")

        print("\n[PASS] scenario_beliefs_edge completed successfully.")

    finally:
        _delete_char(http_client, char_a)
        _delete_char(http_client, char_b)
