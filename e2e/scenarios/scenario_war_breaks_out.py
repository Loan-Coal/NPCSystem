"""
scenario_war_breaks_out.py - WorldState change reflected in dialogue.

Scenario:
  1. Player talks to NPC with world in peace state.
  2. WorldState is updated to war via clock/world-state API.
  3. Player asks the same NPC a question.
  4. Transcript shows whether NPC dialogue changes tone.

No LLM content assertions — this is a manual inspection scenario.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from conftest import TRANSCRIPTS_DIR

SCENARIO_ID = "scenario_war_breaks_out"
NPC = "guard_1"
PLAYER = "player_1"
LOCATION = "loc_gate"


def _post(client: httpx.Client, path: str, payload: dict) -> dict:
    resp = client.post(path, json=payload)
    return {"url": str(resp.url), "status": resp.status_code, "body": resp.json()}


def _write_transcript(lines: list[str], name: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = TRANSCRIPTS_DIR / f"{name}_{ts}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


@pytest.mark.asyncio
def test_war_breaks_out(http_client: httpx.Client) -> None:
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
                "player_message": "Is the road to the capital safe to travel?",
                "location_id": LOCATION,
                "session_id": f"{SCENARIO_ID}:before_war",
            },
        )
        log("Turn 1 — before war (peaceful world state)", r1)

        world_r = _post(
            http_client,
            "/v1/clock/advance",
            {"ticks": 1, "world_state_overrides": {"current_era": "war", "active_conflicts": ["northern_war"]}},
        )
        log("Advance clock with war world-state override", world_r)

        r2 = _post(
            http_client,
            "/v1/dialogue",
            {
                "player_id": PLAYER,
                "npc_id": NPC,
                "player_message": "Is the road to the capital safe to travel?",
                "location_id": LOCATION,
                "session_id": f"{SCENARIO_ID}:after_war",
            },
        )
        log("Turn 2 — after war (should reflect changed world state)", r2)

        transcript.append("## Comparison")
        before_text = r1.get("body", {}).get("npc_response", "")
        after_text = r2.get("body", {}).get("npc_response", "")
        transcript.append(f"**Before war:** {before_text}")
        transcript.append("")
        transcript.append(f"**After war:** {after_text}")
        transcript.append("")

    finally:
        path = _write_transcript(transcript, SCENARIO_ID)
        print(f"\nTranscript written: {path}")
