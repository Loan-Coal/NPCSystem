"""
scenario_goals_edge.py - Edge case coverage for Feature 3.5: Goal nodes.

Covers:
  - urgency=0 and urgency=100 stored correctly (boundary values)
  - all three status values (active, achieved, abandoned) via update
  - status filter correctly returns only matching goals
  - empty status filter returns all goals regardless of status
  - k > total returns all without error
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


def test_goals_edge_cases(http_client: httpx.Client) -> None:
    suffix = uuid.uuid4().hex[:8]
    char_id = f"test_goal_edge_{suffix}"

    _create_char(http_client, char_id, "Goal Edge NPC")

    try:
        # --- Edge case 1: urgency=0 (lower bound) stored correctly ---
        resp = http_client.post(
            f"{_ADMIN}/goals/{char_id}",
            json={"description": "Low priority task.", "urgency": 0},
        )
        assert resp.status_code == 200, resp.text
        id_low = resp.json()["data"]["goal_id"]

        resp = http_client.get(f"{_ADMIN}/goals/{char_id}", params={"k": 10, "status": "active"})
        assert resp.status_code == 200
        goals = resp.json()["data"]["goals"]
        low_goal = next(g for g in goals if g["id"] == id_low)
        assert low_goal["urgency"] == 0, f"urgency=0 not stored: got {low_goal['urgency']}"
        print("[pass] urgency=0 stored correctly")

        # --- Edge case 2: urgency=100 (upper bound) stored correctly ---
        resp = http_client.post(
            f"{_ADMIN}/goals/{char_id}",
            json={"description": "Critical mission.", "urgency": 100},
        )
        assert resp.status_code == 200, resp.text
        id_high = resp.json()["data"]["goal_id"]

        resp = http_client.get(f"{_ADMIN}/goals/{char_id}", params={"k": 10, "status": "active"})
        goals = resp.json()["data"]["goals"]
        high_goal = next(g for g in goals if g["id"] == id_high)
        assert high_goal["urgency"] == 100, f"urgency=100 not stored: got {high_goal['urgency']}"
        print("[pass] urgency=100 stored correctly")

        # --- Edge case 3: create a third goal to abandon ---
        resp = http_client.post(
            f"{_ADMIN}/goals/{char_id}",
            json={"description": "Will be abandoned.", "urgency": 50},
        )
        assert resp.status_code == 200, resp.text
        id_to_abandon = resp.json()["data"]["goal_id"]

        # Update id_high to achieved, id_to_abandon to abandoned
        resp = http_client.patch(f"{_ADMIN}/goals/{id_high}/status", json={"status": "achieved"})
        assert resp.status_code == 200, resp.text
        resp = http_client.patch(f"{_ADMIN}/goals/{id_to_abandon}/status", json={"status": "abandoned"})
        assert resp.status_code == 200, resp.text

        # --- Edge case 4: status=active returns only active goal ---
        resp = http_client.get(f"{_ADMIN}/goals/{char_id}", params={"k": 10, "status": "active"})
        active_goals = resp.json()["data"]["goals"]
        assert len(active_goals) == 1, f"Expected 1 active goal, got {len(active_goals)}"
        assert active_goals[0]["id"] == id_low
        print("[pass] status=active returns only active goals")

        # --- Edge case 5: status=achieved returns only achieved goal ---
        resp = http_client.get(f"{_ADMIN}/goals/{char_id}", params={"k": 10, "status": "achieved"})
        achieved_goals = resp.json()["data"]["goals"]
        assert len(achieved_goals) == 1
        assert achieved_goals[0]["id"] == id_high
        print("[pass] status=achieved returns only achieved goals")

        # --- Edge case 6: status=abandoned returns only abandoned goal ---
        resp = http_client.get(f"{_ADMIN}/goals/{char_id}", params={"k": 10, "status": "abandoned"})
        abandoned_goals = resp.json()["data"]["goals"]
        assert len(abandoned_goals) == 1
        assert abandoned_goals[0]["id"] == id_to_abandon
        print("[pass] status=abandoned returns only abandoned goals")

        # --- Edge case 7: empty status returns all three goals ---
        resp = http_client.get(f"{_ADMIN}/goals/{char_id}", params={"k": 10, "status": ""})
        all_goals = resp.json()["data"]["goals"]
        assert len(all_goals) == 3, f"Empty status should return all 3 goals, got {len(all_goals)}"
        print("[pass] empty status returns all goals regardless of status")

        # --- Edge case 8: k > total returns all without error ---
        resp = http_client.get(f"{_ADMIN}/goals/{char_id}", params={"k": 1000, "status": ""})
        over_k = resp.json()["data"]["goals"]
        assert len(over_k) == 3, f"k=1000 with 3 goals should return 3, got {len(over_k)}"
        print("[pass] k=1000 returns all goals without error")

        print("\n[PASS] scenario_goals_edge completed successfully.")

    finally:
        _delete_char(http_client, char_id)
