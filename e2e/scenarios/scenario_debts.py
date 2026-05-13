"""
scenario_debts.py - E2E scenario for Feature 3.8: Promises and debts.

Requires: running NPC Engine API server (make run).
Run with: python e2e/scenarios/scenario_debts.py

Steps:
  1. Create two Character nodes via the HTTP API.
  2. Create a debt (A owes B a favor).
  3. Fetch debts for A, assert one returned with correct kind and status pending.
  4. Update status to fulfilled.
  5. Fetch debts for A again, assert no pending debts returned.
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

_suffix = uuid.uuid4().hex[:8]
_CHAR_A = f"e2e_debt_char_a_{_suffix}"
_CHAR_B = f"e2e_debt_char_b_{_suffix}"


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
        # Step 1: create characters
        for char_id, name in [(_CHAR_A, "Debt E2E Char A"), (_CHAR_B, "Debt E2E Char B")]:
            resp = client.post(
                f"{_GRAPH}/nodes/Character",
                json={"properties": _char_props(char_id, name)},
            )
            assert resp.status_code == 200, f"Character {name} creation failed: {resp.text}"
        print(f"[seed] Characters {_CHAR_A} and {_CHAR_B} created.")

        try:
            # Step 2: create a debt (A owes B a favor)
            resp = client.post(
                f"{_ADMIN}/debts/{_CHAR_A}",
                json={
                    "creditor_id": _CHAR_B,
                    "kind": "favor",
                    "magnitude": "help with the harvest",
                    "due_by": "",
                },
            )
            assert resp.status_code == 200, resp.text
            print(f"[create] Debt created: {_CHAR_A} owes {_CHAR_B} a favor.")

            # Step 3: fetch debts for A — expect one with kind=favor, status=pending
            resp = client.get(f"{_ADMIN}/debts/{_CHAR_A}")
            assert resp.status_code == 200
            debts = resp.json()["data"]["debts"]

            assert len(debts) == 1, f"Expected 1 debt for A, got {len(debts)}"
            assert debts[0]["kind"] == "favor", (
                f"Expected kind=favor, got {debts[0]['kind']}"
            )
            assert debts[0]["status"] == "pending", (
                f"Expected status=pending, got {debts[0]['status']}"
            )
            assert debts[0]["role"] == "debtor", (
                f"Expected role=debtor, got {debts[0]['role']}"
            )
            print("[assert] 1 pending favor debt returned for A. OK.")

            # Step 4: update status to fulfilled
            resp = client.patch(
                f"{_ADMIN}/debts/{_CHAR_A}/{_CHAR_B}",
                json={"status": "fulfilled"},
            )
            assert resp.status_code == 200, resp.text
            print("[update] Status set to fulfilled.")

            # Step 5: fetch again — now no pending debts for A
            resp = client.get(f"{_ADMIN}/debts/{_CHAR_A}")
            debts_after = resp.json()["data"]["debts"]
            assert len(debts_after) == 0, (
                f"Expected 0 pending debts after fulfillment, got {len(debts_after)}"
            )
            print("[assert] 0 pending debts after fulfillment. OK.")

            print("\n[PASS] scenario_debts completed successfully.")

        finally:
            client.delete(f"{_ADMIN}/graph/characters/{_CHAR_A}")
            client.delete(f"{_ADMIN}/graph/characters/{_CHAR_B}")
            print("[cleanup] Nodes removed.")


if __name__ == "__main__":
    run()
