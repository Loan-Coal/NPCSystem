"""
scenario_memory_consolidation.py - E2E scenario for Feature 3.3: Memory consolidation engine.

Requires: running NPC Engine API server (make run) with a configured LLM backend
          (Ollama or equivalent) to generate the consolidation summary.
Run with: python e2e/scenarios/scenario_memory_consolidation.py

Steps:
  1. Create a Character node via the HTTP API.
  2. Send several dialogue turns to the dialogue API to populate the session store.
  3. Call the admin consolidate endpoint to trigger memory consolidation.
  4. Assert a Memory node was created for the character.
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

_CHAR_ID = f"e2e_consol_char_{uuid.uuid4().hex[:8]}"
_PLAYER_ID = f"e2e_player_{uuid.uuid4().hex[:8]}"

_PLAYER_MESSAGES = [
    "What do you know about the guild?",
    "Do you trust them?",
    "That sounds dangerous.",
    "What will you do about it?",
    "Is there anyone who can help?",
    "How long have you been watching them?",
]


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=_BASE,
        headers={"Authorization": f"Bearer {_KEY}"},
        timeout=60.0,
    )


def _char_props(char_id: str, name: str) -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "id": char_id,
        "name": name,
        "archetype": "schemer",
        "biography": (
            "A figure who has spent years watching the guild's corrupt dealings. "
            "Speaks in careful, measured words and trusts no one easily."
        ),
        "is_player": False,
        "is_active": True,
        "created_at": ts,
        "updated_at": ts,
        "last_graph_updated_at": ts,
        "gossipy": 30,
        "credulity": 40,
        "honesty": 60,
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

        memory_id = None
        try:
            # Step 2: send dialogue turns to populate the session store
            for msg in _PLAYER_MESSAGES:
                resp = client.post(
                    "/v1/dialogue",
                    json={
                        "player_id": _PLAYER_ID,
                        "npc_id": _CHAR_ID,
                        "player_message": msg,
                    },
                )
                assert resp.status_code == 200, f"Dialogue failed: {resp.text}"
            print(f"[seed] {len(_PLAYER_MESSAGES)} dialogue turns submitted.")

            # Step 3: consolidate (turn_threshold=5, we submitted 6 turns)
            resp = client.post(
                f"{_ADMIN}/memories/consolidate/{_CHAR_ID}",
                json={"player_id": _PLAYER_ID, "turn_threshold": 5},
            )
            assert resp.status_code == 200, resp.text
            memory_id = resp.json()["data"]["memory_id"]
            print(f"[consolidate] Memory created: {memory_id}")
            assert memory_id is not None, (
                "Expected a memory_id but got None — "
                "check that the LLM backend is running."
            )

            # Step 4: verify memory exists for the character
            resp = client.get(f"{_ADMIN}/memories/{_CHAR_ID}", params={"k": 5})
            assert resp.status_code == 200
            memories = resp.json()["data"]["memories"]
            mem = next((m for m in memories if m["id"] == memory_id), None)
            assert mem is not None, "Memory node not found in graph"
            assert mem["vividness"] == 75, (
                f"Expected vividness 75, got {mem['vividness']}"
            )
            print(
                f"[verify] Memory vividness={mem['vividness']}, "
                f"content length={len(mem['content'])}."
            )

            print("\n[PASS] scenario_memory_consolidation completed successfully.")

        finally:
            if memory_id:
                client.delete(f"{_ADMIN}/memories/{memory_id}")
            client.delete(f"{_ADMIN}/graph/characters/{_CHAR_ID}")
            print("[cleanup] Test nodes removed.")


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"))
    run()
