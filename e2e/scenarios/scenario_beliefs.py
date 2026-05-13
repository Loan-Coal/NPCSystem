"""
scenario_beliefs.py - E2E scenario for Feature 3.4: Belief nodes.

Requires: running NPC Engine API server (make run).
Run with: python e2e/scenarios/scenario_beliefs.py

Steps:
  1. Create a Character node via the HTTP API.
  2. Create two beliefs via the admin HTTP API.
  3. Fetch beliefs and assert content + confidence (sorted by confidence desc).
  4. Update confidence on one belief.
  5. Cleanup.
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

_CHAR_ID = f"e2e_belief_char_{uuid.uuid4().hex[:8]}"


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

        belief_id_1 = belief_id_2 = None
        try:
            # Step 2: create two beliefs
            resp = client.post(
                f"{_ADMIN}/beliefs/{_CHAR_ID}",
                json={
                    "content": "The merchants guild cannot be trusted.",
                    "confidence": 85,
                },
            )
            assert resp.status_code == 200, resp.text
            belief_id_1 = resp.json()["data"]["belief_id"]

            resp = client.post(
                f"{_ADMIN}/beliefs/{_CHAR_ID}",
                json={
                    "content": "Rain in summer is a bad omen.",
                    "confidence": 60,
                },
            )
            assert resp.status_code == 200, resp.text
            belief_id_2 = resp.json()["data"]["belief_id"]
            print(f"[create] Belief 1: {belief_id_1} | Belief 2: {belief_id_2}")

            # Step 3: fetch and assert
            resp = client.get(f"{_ADMIN}/beliefs/{_CHAR_ID}", params={"k": 5})
            assert resp.status_code == 200
            beliefs = resp.json()["data"]["beliefs"]

            assert len(beliefs) == 2, f"Expected 2 beliefs, got {len(beliefs)}"
            assert beliefs[0]["confidence"] >= beliefs[1]["confidence"], (
                "Expected descending confidence order"
            )
            assert beliefs[0]["id"] == belief_id_1, (
                "Highest-confidence belief should be first"
            )
            print(
                f"[verify] Beliefs fetched and ordered correctly. "
                f"Top confidence: {beliefs[0]['confidence']}"
            )

            # Step 4: update confidence on belief 2
            resp = client.patch(
                f"{_ADMIN}/beliefs/{belief_id_2}/confidence",
                json={"confidence": 90},
            )
            assert resp.status_code == 200, resp.text

            resp = client.get(f"{_ADMIN}/beliefs/{_CHAR_ID}", params={"k": 5})
            beliefs_updated = resp.json()["data"]["beliefs"]
            updated = next(b for b in beliefs_updated if b["id"] == belief_id_2)
            assert updated["confidence"] == 90, (
                f"Expected confidence 90, got {updated['confidence']}"
            )
            print(
                f"[verify] Confidence updated to {updated['confidence']} "
                f"for belief {belief_id_2}."
            )

            print("\n[PASS] scenario_beliefs completed successfully.")

        finally:
            if belief_id_1:
                client.delete(f"{_ADMIN}/beliefs/{belief_id_1}")
            if belief_id_2:
                client.delete(f"{_ADMIN}/beliefs/{belief_id_2}")
            client.delete(f"{_ADMIN}/graph/characters/{_CHAR_ID}")
            print("[cleanup] Test nodes removed.")


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"))
    run()
