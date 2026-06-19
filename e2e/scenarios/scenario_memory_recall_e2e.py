"""
Module: scenario_memory_recall_e2e
Layer: e2e
Purpose: E2E scenario verifying cross-session memory recall (ISSUE-107).

Two-session flow:
  Session 1 — seed a high-arousal memory on an NPC via the admin API, then
              send a dialogue whose player message matches the memory content.
  Session 2 — send a follow-up dialogue in a fresh session_id; assert that
              ``memories_recalled`` in the response is non-empty, proving the
              memory persisted across session boundary and was retrieved.

Requires: running NPC Engine API + Neo4j (make docker-up && make demo-seed).
Run with: python e2e/scenarios/scenario_memory_recall_e2e.py
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
_DIALOGUE = "/v1/dialogue"

_NPC_ID = f"e2e_recall_npc_{uuid.uuid4().hex[:8]}"
_PLAYER_ID = f"e2e_recall_player_{uuid.uuid4().hex[:8]}"
_SESSION_1 = f"sess_{uuid.uuid4().hex[:8]}"
_SESSION_2 = f"sess_{uuid.uuid4().hex[:8]}"
_MEMORY_CONTENT = "The great library burned at midnight and I barely escaped."


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=_BASE,
        headers={"Authorization": f"Bearer {_KEY}"},
        timeout=60.0,
    )


def _char_props(char_id: str, name: str, *, is_player: bool = False) -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "id": char_id,
        "name": name,
        "archetype": "scholar" if not is_player else "adventurer",
        "biography": f"A test character ({name}).",
        "is_player": is_player,
        "is_active": True,
        "created_at": ts,
        "updated_at": ts,
        "last_graph_updated_at": ts,
        "gossipy": 50,
        "credulity": 50,
        "honesty": 50,
    }


def run() -> None:  # noqa: C901 — linear test flow; no abstraction needed
    """Run the two-session memory-recall scenario."""
    with _client() as client:
        # ── Seed NPC and player ──────────────────────────────────────────────
        for char_id, name, is_player in [
            (_NPC_ID, "RecallScholar", False),
            (_PLAYER_ID, "RecallPlayer", True),
        ]:
            resp = client.post(
                f"{_GRAPH}/nodes/Character",
                json={"properties": _char_props(char_id, name, is_player=is_player)},
            )
            assert resp.status_code == 200, f"Character creation failed: {resp.text}"
        print(f"[seed] Characters {_NPC_ID} and {_PLAYER_ID} created.")

        memory_id: str | None = None
        try:
            # ── Session 1: plant a vivid memory on the NPC ──────────────────
            resp = client.post(
                f"{_ADMIN}/memories/from-arousal/{_NPC_ID}",
                json={"content": _MEMORY_CONTENT, "arousal": 90},
            )
            assert resp.status_code == 200, f"Memory creation failed: {resp.text}"
            memory_id = resp.json()["data"]["memory_id"]
            print(f"[session-1] Memory planted: {memory_id}")

            resp = client.post(
                f"{_DIALOGUE}",
                json={
                    "npc_id": _NPC_ID,
                    "player_id": _PLAYER_ID,
                    "player_message": "Tell me what happened at the library.",
                    "session_id": _SESSION_1,
                },
            )
            assert resp.status_code == 200, f"Session-1 dialogue failed: {resp.text}"
            body_1 = resp.json()
            print(f"[session-1] NPC said: {body_1.get('npc_response', '')[:80]!r}")

            # ── Session 2: new session — memory should persist and be recalled ─
            resp = client.post(
                f"{_DIALOGUE}",
                json={
                    "npc_id": _NPC_ID,
                    "player_id": _PLAYER_ID,
                    "player_message": "Do you remember the fire at the library?",
                    "session_id": _SESSION_2,
                },
            )
            assert resp.status_code == 200, f"Session-2 dialogue failed: {resp.text}"
            body_2 = resp.json()
            recalled: list[str] = body_2.get("memories_recalled", [])
            print(f"[session-2] NPC said: {body_2.get('npc_response', '')[:80]!r}")
            print(f"[session-2] memories_recalled: {recalled}")

            assert len(recalled) > 0, (
                "Expected at least one memory ID in memories_recalled for session 2; "
                f"got empty list. NPC response: {body_2.get('npc_response')}"
            )
            assert memory_id in recalled, (
                f"Planted memory {memory_id!r} not found in recalled={recalled!r}"
            )

            print("\n[PASS] scenario_memory_recall_e2e completed successfully.")

        finally:
            if memory_id:
                client.delete(f"{_ADMIN}/memories/{memory_id}")
            client.delete(f"{_ADMIN}/graph/characters/{_NPC_ID}")
            client.delete(f"{_ADMIN}/graph/characters/{_PLAYER_ID}")
            print("[cleanup] Test nodes removed.")


if __name__ == "__main__":
    sys.path.insert(
        0,
        str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"),
    )
    run()
