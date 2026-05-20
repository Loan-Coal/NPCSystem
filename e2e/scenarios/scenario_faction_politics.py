"""
scenario_faction_politics.py - Faction politics engine: standing drift from betrayal event.

Scenario:
  1. Create two factions with an initial standing of 50 (A→B).
  2. Create a character belonging to faction A.
  3. Inject a 'betrayal' event with src_character_id pointing to that character.
  4. Run one tick advance (the faction politics engine will fire).
  5. Assert the A→B standing decreased by 10 (from 50 to 40).
  6. Cleanup.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from conftest import Narrator, api_get, api_post, api_put, char_props

SCENARIO_ID = "scenario_faction_politics"

FAC_A = "fp_faction_alpha"
FAC_B = "fp_faction_beta"
CHAR_A = "fp_char_traitor"
EVENT_ID = "fp_evt_betrayal_001"

INITIAL_STANDING = 50
EXPECTED_DELTA = -10


def test_faction_politics(http_client: httpx.Client) -> None:
    n = Narrator(SCENARIO_ID)
    now = datetime.now(timezone.utc).isoformat()
    admin = "/v1/admin"
    graph = "/v1/graph"

    try:
        n.narrate("Two factions exist. A standing edge (50) links A→B.")

        n.step("Create faction A", api_post(http_client, f"{admin}/factions/", {
            "id": FAC_A, "name": "Faction Alpha", "archetype": "political", "is_active": True,
        }))
        n.step("Create faction B", api_post(http_client, f"{admin}/factions/", {
            "id": FAC_B, "name": "Faction Beta", "archetype": "political", "is_active": True,
        }))

        n.step(f"Set A→B standing to {INITIAL_STANDING}", api_put(
            http_client,
            f"{admin}/factions/{FAC_A}/standings/{FAC_B}",
            {"standing": INITIAL_STANDING},
        ))

        n.narrate("A character joins faction A.")

        n.step("Create character in A", api_post(http_client, f"{graph}/nodes/Character", {
            "properties": char_props(CHAR_A, "The Traitor", is_player=False, now=now),
        }))
        n.step("Add character to faction A", api_post(http_client, f"{admin}/factions/{FAC_A}/members", {
            "character_id": CHAR_A, "role": "member", "status": "active",
        }))

        n.narrate("A betrayal event is injected with src_character_id pointing to the traitor.")

        n.step("Inject betrayal event", api_post(http_client, f"{graph}/nodes/Event", {
            "properties": {
                "id": EVENT_ID,
                "summary": "A member of Faction Alpha betrayed the guild.",
                "severity": 60,
                "location_id": "unknown",
                "occurred_at": now,
                "tick_id": 1,
                "event_type": "betrayal",
                "src_character_id": CHAR_A,
                "is_public": True,
                "last_graph_updated_at": now,
            },
        }))

        n.narrate("One tick advance runs — the faction politics engine fires.")

        n.step("Advance one tick", api_post(http_client, "/v1/clock/advance", {
            "delta_ticks": 1,
            "delta_seconds": 60,
        }))

        n.narrate("Assert A→B standing decreased by 10.")

        get_resp = api_get(http_client, f"{admin}/factions/{FAC_A}/standings")
        n.step("Read standings for A", get_resp)

        standings = get_resp["body"].get("data", [])
        a_to_b = next(
            (s for s in standings if s.get("target", {}).get("id") == FAC_B),
            None,
        )
        assert a_to_b is not None, f"Expected A→B standing entry; got: {standings}"
        actual = a_to_b["standing"]
        expected = INITIAL_STANDING + EXPECTED_DELTA
        assert actual == expected, (
            f"Expected A→B standing={expected} after betrayal; got {actual}"
        )

    finally:
        n.save()
