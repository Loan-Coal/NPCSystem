"""
scenario_tavern_secret.py - Gossip propagation scenario.

Scenario:
  1. Player tells NPC A a secret at the tavern.
  2. Clock tick runs so gossip propagation fires.
  3. Player asks NPC B (in same location) if they heard anything.
  4. Transcript is written whether or not NPC B's response mentions the secret.

No LLM content assertions — this is a manual inspection scenario.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from conftest import TRANSCRIPTS_DIR

SCENARIO_ID = "scenario_tavern_secret"
NPC_A = "merchant_1"
NPC_B = "guard_1"
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
def test_tavern_secret(http_client: httpx.Client) -> None:
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
        r = _post(
            http_client,
            "/v1/dialogue",
            {
                "player_id": PLAYER,
                "npc_id": NPC_A,
                "player_message": "I heard the blacksmith is selling stolen goods.",
                "location_id": LOCATION,
                "session_id": f"{SCENARIO_ID}:turn1",
            },
        )
        log("Turn 1 — player tells NPC A the secret", r)

        clock_r = _post(http_client, "/v1/clock/advance", {"ticks": 1})
        log("Clock advance (gossip tick)", clock_r)

        r2 = _post(
            http_client,
            "/v1/dialogue",
            {
                "player_id": PLAYER,
                "npc_id": NPC_B,
                "player_message": "Have you heard any interesting rumors lately?",
                "location_id": LOCATION,
                "session_id": f"{SCENARIO_ID}:turn2",
            },
        )
        log("Turn 2 — player asks NPC B about rumors", r2)

    finally:
        path = _write_transcript(transcript, SCENARIO_ID)
        print(f"\nTranscript written: {path}")
