"""
scenario_factional_rumor.py - Faction-aware gossip propagation scenario.

Scenario:
  1. Create two factions (allies) and two hostile factions with standing edges.
  2. Create four NPCs: two in each faction, all co-located.
  3. Seed an event and KNOWS_ABOUT edges for one NPC in each pair.
  4. Run two gossip ticks via the admin tick endpoint.
  5. Log which pairs propagated and their distortion levels.

No LLM content assertions — this is a manual inspection scenario.
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

SCENARIO_ID = "scenario_factional_rumor"

FAC_ALLIED_A = "fac_allied_a"
FAC_ALLIED_B = "fac_allied_b"
FAC_HOSTILE_A = "fac_hostile_x"
FAC_HOSTILE_B = "fac_hostile_y"

NPC_ALLIED_1 = "npc_fac_ally1"
NPC_ALLIED_2 = "npc_fac_ally2"
NPC_HOSTILE_1 = "npc_fac_hos1"
NPC_HOSTILE_2 = "npc_fac_hos2"

LOCATION = "loc_plaza"
EVENT_ID = "evt_factional_rumor"


def _post(client: httpx.Client, path: str, payload: dict) -> dict:
    resp = client.post(path, json=payload)
    return {"url": str(resp.url), "status": resp.status_code, "body": resp.json()}


def _put(client: httpx.Client, path: str, payload: dict) -> dict:
    resp = client.put(path, json=payload)
    return {"url": str(resp.url), "status": resp.status_code, "body": resp.json()}


def _write_transcript(lines: list[str], name: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = TRANSCRIPTS_DIR / f"{name}_{ts}.md"
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


@pytest.mark.asyncio
def test_factional_rumor(http_client: httpx.Client) -> None:
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

    try:
        # --- Factions ---
        log("Create faction allied_a", _post(http_client, f"{admin}/factions/", {
            "id": FAC_ALLIED_A, "name": "Allied Faction A", "archetype": "political", "is_active": True,
        }))
        log("Create faction allied_b", _post(http_client, f"{admin}/factions/", {
            "id": FAC_ALLIED_B, "name": "Allied Faction B", "archetype": "political", "is_active": True,
        }))
        log("Create faction hostile_x", _post(http_client, f"{admin}/factions/", {
            "id": FAC_HOSTILE_A, "name": "Hostile Faction X", "archetype": "military", "is_active": True,
        }))
        log("Create faction hostile_y", _post(http_client, f"{admin}/factions/", {
            "id": FAC_HOSTILE_B, "name": "Hostile Faction Y", "archetype": "military", "is_active": True,
        }))

        # Standing: allied factions like each other, hostile factions hate each other
        log("Set allied standing A→B", _put(http_client, f"{admin}/factions/{FAC_ALLIED_A}/standings/{FAC_ALLIED_B}", {"standing": 80}))
        log("Set allied standing B→A", _put(http_client, f"{admin}/factions/{FAC_ALLIED_B}/standings/{FAC_ALLIED_A}", {"standing": 80}))
        log("Set hostile standing X→Y", _put(http_client, f"{admin}/factions/{FAC_HOSTILE_A}/standings/{FAC_HOSTILE_B}", {"standing": -100}))
        log("Set hostile standing Y→X", _put(http_client, f"{admin}/factions/{FAC_HOSTILE_B}/standings/{FAC_HOSTILE_A}", {"standing": -100}))

        # --- Characters ---
        for npc_id, faction_id in [
            (NPC_ALLIED_1, FAC_ALLIED_A),
            (NPC_ALLIED_2, FAC_ALLIED_B),
            (NPC_HOSTILE_1, FAC_HOSTILE_A),
            (NPC_HOSTILE_2, FAC_HOSTILE_B),
        ]:
            log(
                f"Create NPC {npc_id}",
                _post(http_client, f"{admin}/characters/", {
                    "id": npc_id,
                    "name": npc_id,
                    "location_id": LOCATION,
                    "is_player": False,
                    "is_active": True,
                    "honesty": 50,
                    "gossipy": 80,
                }),
            )
            log(
                f"Add {npc_id} → {faction_id}",
                _post(http_client, f"{admin}/factions/{faction_id}/members", {
                    "character_id": npc_id, "role": "member", "status": "active",
                }),
            )

        # --- Gossip ticks ---
        for tick in [1, 2]:
            log(
                f"Gossip tick {tick}",
                _post(http_client, f"{admin}/batch/gossip", {"tick_id": 1000 + tick, "max_pairs": 10}),
            )

        path = _write_transcript(transcript, SCENARIO_ID)
        print(f"\nTranscript written to {path}")

    except Exception as exc:
        transcript.append(f"## ERROR\n```\n{exc}\n```")
        path = _write_transcript(transcript, f"{SCENARIO_ID}_ERROR")
        print(f"\nError transcript written to {path}")
        raise
