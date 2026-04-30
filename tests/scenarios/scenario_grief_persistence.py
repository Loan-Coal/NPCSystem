"""
scenario_grief_persistence.py - Emotion persistence across turns.

Scenario:
  1. Player delivers bad news (death of a loved one) to NPC.
  2. Player talks to the same NPC again the following turn.
  3. Transcript shows whether the NPC's mood/response reflects the prior grief.

No LLM content assertions — this is a manual inspection scenario.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from conftest import TRANSCRIPTS_DIR

SCENARIO_ID = "scenario_grief_persistence"
NPC = "elder_1"
PLAYER = "player_1"
LOCATION = "loc_market"


def _post(client: httpx.Client, path: str, payload: dict) -> dict:
    resp = client.post(path, json=payload)
    return {"url": str(resp.url), "status": resp.status_code, "body": resp.json()}


def _write_transcript(lines: list[str], name: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = TRANSCRIPTS_DIR / f"{name}_{ts}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


@pytest.mark.asyncio
def test_grief_persistence(http_client: httpx.Client) -> None:
    session_id = f"{SCENARIO_ID}:{PLAYER}:{NPC}"
    transcript: list[str] = [
        f"# Transcript: {SCENARIO_ID}",
        f"_Generated at {datetime.now(timezone.utc).isoformat()}_",
        "",
    ]

    def log(step: str, call: dict) -> None:
        transcript.append(f"## {step}")
        transcript.append(f"```json\n{json.dumps(call, indent=2)}\n```")
        transcript.append("")

    try:
        r1 = _post(
            http_client,
            "/v1/dialogue",
            {
                "player_id": PLAYER,
                "npc_id": NPC,
                "player_message": "Elder, my daughter passed away last night. She was only seven.",
                "location_id": LOCATION,
                "session_id": session_id,
            },
        )
        log("Turn 1 — delivering grief", r1)

        npc_state_r = http_client.get(f"/v1/npc/{NPC}/state")
        log("NPC state after turn 1", {"status": npc_state_r.status_code, "body": npc_state_r.json()})

        r2 = _post(
            http_client,
            "/v1/dialogue",
            {
                "player_id": PLAYER,
                "npc_id": NPC,
                "player_message": "I came back to talk. I still feel so lost.",
                "location_id": LOCATION,
                "session_id": session_id,
            },
        )
        log("Turn 2 — follow-up (emotion should persist)", r2)

        npc_state_r2 = http_client.get(f"/v1/npc/{NPC}/state")
        log("NPC state after turn 2", {"status": npc_state_r2.status_code, "body": npc_state_r2.json()})

    finally:
        path = _write_transcript(transcript, SCENARIO_ID)
        print(f"\nTranscript written: {path}")
