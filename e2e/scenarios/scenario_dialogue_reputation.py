"""
scenario_dialogue_reputation.py - Reputation-aware dialogue tone.

Scenario:
  1. Create a guild faction and an NPC member.
  2. Player reputation with the guild starts at +80 (trusted ally).
  3. Player asks for a favour — NPC should be warm and cooperative.
  4. Reputation is dropped to -80 (hostile).
  5. Same request is made — NPC tone should be cold or suspicious.
  6. Transcript captures both responses for side-by-side comparison.

No LLM content assertions — manual inspection scenario.
Uses the LLM adapter configured in the running stack.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from conftest import Narrator, api_post, api_put, char_props, loc_props

SCENARIO_ID = "scenario_dialogue_reputation"

FACTION_ID = "repd_guild"
NPC_ID = "repd_guildmaster"
PLAYER_ID = "player_1"
LOCATION = "loc_market"


def test_dialogue_reputation(http_client: httpx.Client) -> None:
    n = Narrator(SCENARIO_ID)
    now = datetime.now(timezone.utc).isoformat()
    admin = "/v1/admin"
    graph = "/v1/graph"

    try:
        n.narrate("Setting up the guild and its guildmaster.")

        n.step("Create guild faction", api_post(http_client, f"{admin}/factions/", {
            "id": FACTION_ID, "name": "The Merchant Guild", "archetype": "mercantile", "is_active": True,
        }))
        n.step("Create guildmaster NPC", api_post(http_client, f"{graph}/nodes/Character", {
            "properties": char_props(
                NPC_ID, "Guildmaster Vance",
                is_player=False,
                archetype="merchant",
                biography="Head of the Merchant Guild. Values loyalty above all.",
                gossipy=40, credulity=30, honesty=70,
                now=now,
            ),
        }))
        n.step("Guildmaster joins faction", api_post(http_client, f"{admin}/factions/{FACTION_ID}/members", {
            "character_id": NPC_ID, "role": "leader", "status": "active",
        }))
        n.step("Place guildmaster at market", api_post(http_client, f"{graph}/edges/LOCATED_AT", {
            "src_id": NPC_ID, "dst_id": LOCATION,
            "properties": {"is_permanent_resident": True, "arrived_at": now},
        }))

        n.narrate("Player has earned deep trust with the guild (standing +80).")

        n.step("Set player reputation +80 (ally)", api_put(http_client,
            f"{admin}/characters/{PLAYER_ID}/reputation/{FACTION_ID}", {"standing": 80}))

        n.step("Dialogue — player asks for help (allied)", api_post(http_client, "/v1/dialogue", {
            "player_id": PLAYER_ID,
            "npc_id": NPC_ID,
            "player_message": "Vance, I need access to the guild warehouse tonight. Can you arrange it?",
            "location_id": LOCATION,
            "session_id": f"{SCENARIO_ID}:allied",
        }))

        n.narrate("Relations sour. Player reputation drops to -80 (hostile).")

        n.step("Set player reputation -80 (hostile)", api_put(http_client,
            f"{admin}/characters/{PLAYER_ID}/reputation/{FACTION_ID}", {"standing": -80}))

        n.step("Dialogue — same request (hostile)", api_post(http_client, "/v1/dialogue", {
            "player_id": PLAYER_ID,
            "npc_id": NPC_ID,
            "player_message": "Vance, I need access to the guild warehouse tonight. Can you arrange it?",
            "location_id": LOCATION,
            "session_id": f"{SCENARIO_ID}:hostile",
        }))

        n.narrate("Compare both responses above — tone should differ with reputation.")

    finally:
        n.save()
