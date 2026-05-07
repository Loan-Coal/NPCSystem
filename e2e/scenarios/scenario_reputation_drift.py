"""
scenario_reputation_drift.py - Reputation drift scenario via admin API.

Scenario:
  1. Create a faction, NPC member, and player character.
  2. Set player reputation with the faction to 60 (friendly).
  3. Adjust reputation down by 90 (should clamp to -30).
  4. Verify final standing via GET endpoint.

No LLM content assertions — this is a data-plane correctness scenario.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

try:
    from conftest import TRANSCRIPTS_DIR  # type: ignore[import]
except ImportError:
    TRANSCRIPTS_DIR = Path(__file__).parent / "transcripts"

SCENARIO_ID = "scenario_reputation_drift"

FACTION_ID = "rep_test_faction"
NPC_ID = "rep_test_npc"
PLAYER_ID = "rep_test_player"


def _post(client: httpx.Client, path: str, payload: dict) -> dict:
    resp = client.post(path, json=payload)
    return {"url": str(resp.url), "status": resp.status_code, "body": resp.json()}


def _put(client: httpx.Client, path: str, payload: dict) -> dict:
    resp = client.put(path, json=payload)
    return {"url": str(resp.url), "status": resp.status_code, "body": resp.json()}


def _get(client: httpx.Client, path: str) -> dict:
    resp = client.get(path)
    return {"url": str(resp.url), "status": resp.status_code, "body": resp.json()}


def _write_transcript(lines: list[str], name: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = TRANSCRIPTS_DIR / f"{name}_{ts}.md"
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


@pytest.mark.asyncio
def test_reputation_drift(http_client: httpx.Client) -> None:
    transcript: list[str] = [
        f"# Transcript: {SCENARIO_ID}",
        f"_Generated at {datetime.now(timezone.utc).isoformat()}_",
        "",
    ]

    def log(step: str, call: dict) -> None:
        transcript.append(f"## {step}")
        transcript.append(f"```json\n{json.dumps(call, indent=2)}\n```")
        transcript.append("")

    admin = "/v1/admin"
    graph = "/v1/graph"

    try:
        log("Create faction", _post(http_client, f"{admin}/factions/", {
            "id": FACTION_ID, "name": "Test Faction", "archetype": "political", "is_active": True,
        }))

        log("Create NPC", _post(http_client, f"{admin}/characters/", {
            "id": NPC_ID, "name": "NPC", "location_id": "rep_loc",
            "is_player": False, "is_active": True,
        }))
        log("NPC joins faction", _post(http_client, f"{admin}/factions/{FACTION_ID}/members", {
            "character_id": NPC_ID, "role": "member", "status": "active",
        }))

        log("Create player", _post(http_client, f"{admin}/characters/", {
            "id": PLAYER_ID, "name": "Player", "location_id": "rep_loc",
            "is_player": True, "is_active": True,
        }))

        # Set initial reputation
        log("Set reputation 60", _put(http_client,
            f"{admin}/characters/{PLAYER_ID}/reputation/{FACTION_ID}", {"standing": 60}))

        # Read back
        log("Read reputation", _get(http_client,
            f"{graph}/characters/{PLAYER_ID}/reputation/{FACTION_ID}"))

        # Adjust down by 90 → should clamp to -30
        log("Adjust -90", _post(http_client,
            f"{admin}/characters/{PLAYER_ID}/reputation/{FACTION_ID}/adjust", {"delta": -90}))

        # Final read
        final = _get(http_client, f"{graph}/characters/{PLAYER_ID}/reputation/{FACTION_ID}")
        log("Final reputation", final)

        assert final["body"]["data"]["standing"] == -30, (
            f"Expected -30, got {final['body']['data']['standing']}"
        )

        path = _write_transcript(transcript, SCENARIO_ID)
        print(f"\nTranscript written to {path}")

    except Exception as exc:
        transcript.append(f"## ERROR\n```\n{exc}\n```")
        path = _write_transcript(transcript, f"{SCENARIO_ID}_ERROR")
        print(f"\nError transcript written to {path}")
        raise
