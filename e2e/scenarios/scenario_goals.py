"""
scenario_goals.py - E2E scenario for Feature 3.5: Goal nodes.

Requires: running NPC Engine API server (make run).
Run with: python e2e/scenarios/scenario_goals.py

Steps:
  1. Create a Character node via the HTTP API.
  2. Create two goals: one active, one achieved.
  3. Fetch active goals and assert only one returned.
  4. Update the active goal's status to achieved.
  5. Fetch active goals again and assert empty.
  6. Cleanup.
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

_CHAR_ID = f"e2e_goal_char_{uuid.uuid4().hex[:8]}"


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
        # Step 1: create character
        resp = client.post(
            f"{_GRAPH}/nodes/Character",
            json={"properties": _char_props(_CHAR_ID, "E2E NPC")},
        )
        assert resp.status_code == 200, f"Character creation failed: {resp.text}"
        print(f"[seed] Character {_CHAR_ID} created.")

        goal_id_active = goal_id_achieved = None
        try:
            # Step 2: create one active goal
            resp = client.post(
                f"{_ADMIN}/goals/{_CHAR_ID}",
                json={"description": "Find the stolen amulet.", "urgency": 80},
            )
            assert resp.status_code == 200, resp.text
            goal_id_active = resp.json()["data"]["goal_id"]

            # Create second goal and immediately set it to achieved
            resp = client.post(
                f"{_ADMIN}/goals/{_CHAR_ID}",
                json={"description": "Deliver the message to the mayor.", "urgency": 40},
            )
            assert resp.status_code == 200, resp.text
            goal_id_achieved = resp.json()["data"]["goal_id"]

            resp = client.patch(
                f"{_ADMIN}/goals/{goal_id_achieved}/status",
                json={"status": "achieved"},
            )
            assert resp.status_code == 200, resp.text
            print(
                f"[create] Active goal: {goal_id_active} | "
                f"Achieved goal: {goal_id_achieved}"
            )

            # Step 3: fetch active goals — should return only 1
            resp = client.get(
                f"{_ADMIN}/goals/{_CHAR_ID}", params={"k": 10, "status": "active"}
            )
            assert resp.status_code == 200
            active_goals = resp.json()["data"]["goals"]

            assert len(active_goals) == 1, (
                f"Expected 1 active goal, got {len(active_goals)}"
            )
            assert active_goals[0]["id"] == goal_id_active
            assert active_goals[0]["status"] == "active"
            print(
                f"[verify] One active goal returned: {active_goals[0]['description']}"
            )

            # Step 4: update the active goal to achieved
            resp = client.patch(
                f"{_ADMIN}/goals/{goal_id_active}/status",
                json={"status": "achieved"},
            )
            assert resp.status_code == 200, resp.text
            print(f"[update] Goal {goal_id_active} marked as achieved.")

            # Step 5: fetch active goals again — should be empty
            resp = client.get(
                f"{_ADMIN}/goals/{_CHAR_ID}", params={"k": 10, "status": "active"}
            )
            active_goals_after = resp.json()["data"]["goals"]
            assert len(active_goals_after) == 0, (
                f"Expected 0 active goals after update, got {len(active_goals_after)}"
            )
            print("[verify] No active goals remain after update.")

            print("\n[PASS] scenario_goals completed successfully.")

        finally:
            if goal_id_active:
                client.delete(f"{_ADMIN}/goals/{goal_id_active}")
            if goal_id_achieved:
                client.delete(f"{_ADMIN}/goals/{goal_id_achieved}")
            client.delete(f"{_ADMIN}/graph/characters/{_CHAR_ID}")
            print("[cleanup] Test nodes removed.")


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"))
    run()
