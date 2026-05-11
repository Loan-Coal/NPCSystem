"""
scenario_war_breaks_out.py - WorldState change reflected in dialogue.

Scenario:
  1. Player asks a guard about road safety during peace.
  2. WorldState node is updated to represent a war epoch.
  3. Player asks the same question again.
  4. Transcript shows whether NPC tone shifts from reassuring to cautious.

No LLM content assertions — manual inspection scenario.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from conftest import Narrator, api_post

SCENARIO_ID = "scenario_war_breaks_out"
NPC = "guard_1"
PLAYER = "player_1"
LOCATION = "loc_gate"


def test_war_breaks_out(http_client: httpx.Client) -> None:
    n = Narrator(SCENARIO_ID)
    now = datetime.now(timezone.utc).isoformat()
    graph = "/v1/graph"

    try:
        n.narrate("World is at peace. Player asks about road safety.")

        n.step("Turn 1 — before war (peaceful world state)", api_post(http_client, "/v1/dialogue", {
            "player_id": PLAYER,
            "npc_id": NPC,
            "player_message": "Is the road to the capital safe to travel?",
            "location_id": LOCATION,
            "session_id": f"{SCENARIO_ID}:before_war",
        }))

        n.narrate("War breaks out. WorldState node is updated.")

        n.step("Upsert WorldState — war epoch", api_post(http_client, f"{graph}/nodes/world_state", {
            "properties": {
                "id": "world",
                "epoch": "war",
                "faction_standings": {},
                "active_conditions": ["northern_war"],
                "weather": "overcast",
                "time_of_day": "morning",
                "last_updated_at": now,
                "last_graph_updated_at": now,
            },
        }))

        n.narrate("Same question. Does the guard reflect the new danger?")

        n.step("Turn 2 — after war (tone should shift)", api_post(http_client, "/v1/dialogue", {
            "player_id": PLAYER,
            "npc_id": NPC,
            "player_message": "Is the road to the capital safe to travel?",
            "location_id": LOCATION,
            "session_id": f"{SCENARIO_ID}:after_war",
        }))

    finally:
        n.save()
