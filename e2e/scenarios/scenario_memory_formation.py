"""
scenario_memory_formation.py - E2E scenario for Feature 3.2: Memory nodes and formation.

Requires: running NPC Engine API server (make run).
Run with: python e2e/scenarios/scenario_memory_formation.py

Steps:
  1. Create a Character node via the HTTP API.
  2. Create a Memory via the from-arousal endpoint (high-arousal path, arousal=90).
  3. Assert the Memory exists with vividness=80.
  4. Trigger vividness decay via the admin decay endpoint.
  5. Assert vividness has decreased by 5 (clamped to 0 minimum).
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

_CHAR_ID = f"e2e_mem_char_{uuid.uuid4().hex[:8]}"
_MEM_CONTENT = "The player threatened the innkeeper in front of the guard."


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
            json={"properties": _char_props(_CHAR_ID, "Test NPC")},
        )
        assert resp.status_code == 200, f"Character creation failed: {resp.text}"
        print(f"[seed] Character {_CHAR_ID} created.")

        memory_id = None
        try:
            # Step 2: create memory via from-arousal (arousal=90 → above threshold)
            resp = client.post(
                f"{_ADMIN}/memories/from-arousal/{_CHAR_ID}",
                json={"content": _MEM_CONTENT, "arousal": 90},
            )
            assert resp.status_code == 200, resp.text
            memory_id = resp.json()["data"]["memory_id"]
            print(f"[create] Memory created: {memory_id}")
            assert memory_id is not None, "Memory should have been created for arousal=90"

            # Step 3: verify memory exists with expected initial vividness
            resp = client.get(f"{_ADMIN}/memories/{_CHAR_ID}", params={"k": 10})
            assert resp.status_code == 200
            memories = resp.json()["data"]["memories"]
            mem = next((m for m in memories if m["id"] == memory_id), None)
            assert mem is not None, "Memory node not found"
            initial_vividness = mem["vividness"]
            print(f"[verify] Memory vividness before decay: {initial_vividness}")
            assert initial_vividness == 80, (
                f"Expected vividness 80, got {initial_vividness}"
            )

            # Step 4: trigger vividness decay (5 per day by default)
            resp = client.post(
                f"{_ADMIN}/memories/decay", json={"decay_per_day": 5}
            )
            assert resp.status_code == 200, resp.text
            affected = resp.json()["data"]["decayed_count"]
            print(f"[decay] Vividness decay ran, {affected} node(s) affected.")
            assert affected >= 1, "At least one Memory node should have been decayed"

            # Step 5: verify vividness decreased by 5
            resp = client.get(f"{_ADMIN}/memories/{_CHAR_ID}", params={"k": 10})
            memories_after = resp.json()["data"]["memories"]
            mem_after = next((m for m in memories_after if m["id"] == memory_id), None)
            assert mem_after is not None
            decayed_vividness = mem_after["vividness"]
            print(f"[verify] Memory vividness after decay: {decayed_vividness}")
            assert decayed_vividness == initial_vividness - 5, (
                f"Expected vividness {initial_vividness - 5}, got {decayed_vividness}"
            )

            print("\n[PASS] scenario_memory_formation completed successfully.")

        finally:
            if memory_id:
                client.delete(f"{_ADMIN}/memories/{memory_id}")
            client.delete(f"{_ADMIN}/graph/characters/{_CHAR_ID}")
            print("[cleanup] Test nodes removed.")


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"))
    run()
