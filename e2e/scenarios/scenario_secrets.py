"""
scenario_secrets.py - E2E scenario for Feature 3.7: Secret nodes.

Requires: running NPC Engine API server (make run).
Run with: python e2e/scenarios/scenario_secrets.py

Steps:
  1. Create a Character node via the HTTP API.
  2. Create a secret for that character.
  3. Fetch secrets, assert one returned with correct severity.
  4. Cleanup.
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

_CHAR_ID = f"e2e_secret_char_{uuid.uuid4().hex[:8]}"


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
            json={"properties": _char_props(_CHAR_ID, "E2E Secret Keeper")},
        )
        assert resp.status_code == 200, f"Character creation failed: {resp.text}"
        print(f"[seed] Character {_CHAR_ID} created.")

        secret_id = None
        try:
            # Step 2: create a secret
            resp = client.post(
                f"{_ADMIN}/secrets/{_CHAR_ID}",
                json={
                    "content": "The duke is planning to poison the king.",
                    "severity": 90,
                },
            )
            assert resp.status_code == 200, resp.text
            secret_id = resp.json()["data"]["secret_id"]
            print(f"[create] Secret {secret_id} created for {_CHAR_ID}.")

            # Step 3: fetch secrets — expect one with severity 90
            resp = client.get(f"{_ADMIN}/secrets/{_CHAR_ID}", params={"k": 5})
            assert resp.status_code == 200
            secrets = resp.json()["data"]["secrets"]

            assert len(secrets) == 1, f"Expected 1 secret, got {len(secrets)}"
            assert secrets[0]["severity"] == 90, (
                f"Expected severity 90, got {secrets[0]['severity']}"
            )
            assert "duke" in secrets[0]["content"].lower(), "Content mismatch"
            print("[assert] 1 secret returned with severity 90. OK.")

            print("\n[PASS] scenario_secrets completed successfully.")

        finally:
            if secret_id:
                client.delete(f"{_ADMIN}/secrets/{secret_id}")
            client.delete(f"{_ADMIN}/graph/characters/{_CHAR_ID}")
            print("[cleanup] Test nodes removed.")


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"))
    run()
