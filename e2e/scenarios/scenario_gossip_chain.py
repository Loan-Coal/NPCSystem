"""
scenario_gossip_chain.py - Event awareness and gossip propagation chain.

Scenario:
  1. Create an event at loc_market. NPC at that location gets a KNOWS_ABOUT edge.
  2. A related NPC (different location, knows the first via RELATES_TO) doesn't know yet.
  3. Run a gossip tick.
  4. Check whether the second NPC's state now includes the event (knowledge spread).
  5. Run a second tick — check for further spread or distortion.

Uses seeded world data (player_1, npc_1, npc_6 all connected via RELATES_TO).
No LLM content assertions — data-plane propagation scenario.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from conftest import Narrator, api_get, api_post

SCENARIO_ID = "scenario_gossip_chain"

EVENT_ID = "evt_gossip_chain"
KNOWS_NPC = "npc_1"        # Aldric — at loc_market, gossipy=70; seeded via api_seeder
DISTANT_NPC = "npc_6"      # Ivor  — at loc_market too; knows npc_1 via RELATES_TO
LOCATION = "loc_market"


def test_gossip_chain(http_client: httpx.Client) -> None:
    n = Narrator(SCENARIO_ID)
    now = datetime.now(timezone.utc).isoformat()
    graph = "/v1/graph"
    admin = "/v1/admin"

    try:
        n.narrate(f"A dramatic event occurs at {LOCATION}. Only {KNOWS_NPC} witnesses it.")

        n.step("Upsert event", api_post(http_client, f"{graph}/nodes/Event", {
            "properties": {
                "id": EVENT_ID,
                "summary": "A cloaked figure was seen exchanging a mysterious package at the market stalls.",
                "severity": 65,
                "location_id": LOCATION,
                "occurred_at": now,
                "tick_id": 500,
                "event_type": "crime",
                "is_public": False,
                "last_graph_updated_at": now,
            },
        }))

        n.step(f"{KNOWS_NPC} KNOWS_ABOUT the event", api_post(http_client, f"{graph}/edges/KNOWS_ABOUT", {
            "src_id": KNOWS_NPC, "dst_id": EVENT_ID,
            "properties": {"knowledge_state": "knows", "learned_at_tick": 500},
        }))

        n.narrate(f"Before gossip tick — inspect {DISTANT_NPC}'s known events.")

        n.step(f"{DISTANT_NPC} NPC state (before gossip)", api_get(http_client, f"/v1/npc/{DISTANT_NPC}/state"))

        n.narrate("Gossip tick fires. Aldric may share what he saw with Ivor.")

        n.step("Gossip tick 1", api_post(http_client, f"{admin}/batch/gossip_tick", {
            "tick_override": 501, "max_pairs": 20,
        }))

        n.step(f"{DISTANT_NPC} NPC state (after tick 1)", api_get(http_client, f"/v1/npc/{DISTANT_NPC}/state"))

        n.narrate("Second tick — knowledge may spread further or become distorted.")

        n.step("Gossip tick 2", api_post(http_client, f"{admin}/batch/gossip_tick", {
            "tick_override": 502, "max_pairs": 20,
        }))

        n.step(f"{DISTANT_NPC} NPC state (after tick 2)", api_get(http_client, f"/v1/npc/{DISTANT_NPC}/state"))

        n.narrate("Check the originator's NPC state too — distortion_type on edges tells the story.")
        n.step(f"{KNOWS_NPC} NPC state (final)", api_get(http_client, f"/v1/npc/{KNOWS_NPC}/state"))

    finally:
        n.save()
