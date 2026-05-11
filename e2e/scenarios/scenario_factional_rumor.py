"""
scenario_factional_rumor.py - Faction-aware gossip propagation.

Scenario:
  1. Create two allied factions and two hostile factions with standing edges.
  2. Create four NPCs: two in each faction, all co-located.
  3. Seed an event and KNOWS_ABOUT edges for one NPC in each pair.
  4. Run two gossip ticks via the admin batch endpoint.
  5. Observe which pairs propagated and their distortion levels.

No LLM content assertions — manual inspection scenario.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from conftest import Narrator, api_post, api_put, char_props, loc_props

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


def test_factional_rumor(http_client: httpx.Client) -> None:
    n = Narrator(SCENARIO_ID)
    now = datetime.now(timezone.utc).isoformat()
    admin = "/v1/admin"
    graph = "/v1/graph"

    try:
        n.narrate("Two factions are allied; two others are hostile to each other.")

        n.step("Create faction allied_a", api_post(http_client, f"{admin}/factions/", {
            "id": FAC_ALLIED_A, "name": "Allied Faction A", "archetype": "political", "is_active": True,
        }))
        n.step("Create faction allied_b", api_post(http_client, f"{admin}/factions/", {
            "id": FAC_ALLIED_B, "name": "Allied Faction B", "archetype": "political", "is_active": True,
        }))
        n.step("Create faction hostile_x", api_post(http_client, f"{admin}/factions/", {
            "id": FAC_HOSTILE_A, "name": "Hostile Faction X", "archetype": "military", "is_active": True,
        }))
        n.step("Create faction hostile_y", api_post(http_client, f"{admin}/factions/", {
            "id": FAC_HOSTILE_B, "name": "Hostile Faction Y", "archetype": "military", "is_active": True,
        }))

        n.step("Standing allied A→B (+80)", api_put(http_client, f"{admin}/factions/{FAC_ALLIED_A}/standings/{FAC_ALLIED_B}", {"standing": 80}))
        n.step("Standing allied B→A (+80)", api_put(http_client, f"{admin}/factions/{FAC_ALLIED_B}/standings/{FAC_ALLIED_A}", {"standing": 80}))
        n.step("Standing hostile X→Y (-100)", api_put(http_client, f"{admin}/factions/{FAC_HOSTILE_A}/standings/{FAC_HOSTILE_B}", {"standing": -100}))
        n.step("Standing hostile Y→X (-100)", api_put(http_client, f"{admin}/factions/{FAC_HOSTILE_B}/standings/{FAC_HOSTILE_A}", {"standing": -100}))

        n.narrate("NPCs gather at the plaza.")

        n.step("Upsert location (plaza)", api_post(http_client, f"{graph}/nodes/Location", {
            "properties": loc_props(LOCATION, "The Plaza", location_tag="plaza", now=now),
        }))

        for npc_id, faction_id, gossip in [
            (NPC_ALLIED_1, FAC_ALLIED_A, 80),
            (NPC_ALLIED_2, FAC_ALLIED_B, 80),
            (NPC_HOSTILE_1, FAC_HOSTILE_A, 80),
            (NPC_HOSTILE_2, FAC_HOSTILE_B, 80),
        ]:
            n.step(f"Create NPC {npc_id}", api_post(http_client, f"{graph}/nodes/Character", {
                "properties": char_props(npc_id, npc_id, is_player=False, gossipy=gossip, now=now),
            }))
            n.step(f"{npc_id} LOCATED_AT plaza", api_post(http_client, f"{graph}/edges/LOCATED_AT", {
                "src_id": npc_id, "dst_id": LOCATION,
                "properties": {"is_permanent_resident": False, "arrived_at": now},
            }))
            n.step(f"{npc_id} joins {faction_id}", api_post(http_client, f"{admin}/factions/{faction_id}/members", {
                "character_id": npc_id, "role": "member", "status": "active",
            }))

        n.narrate("An event occurs. Only one NPC per pair witnesses it directly.")

        n.step("Upsert event", api_post(http_client, f"{graph}/nodes/Event", {
            "properties": {
                "id": EVENT_ID, "summary": "A mysterious fire broke out at the east wall.",
                "severity": 80, "location_id": LOCATION, "occurred_at": now,
                "tick_id": 1, "event_type": "crime", "is_public": True,
                "last_graph_updated_at": now,
            },
        }))

        for npc_id in [NPC_ALLIED_1, NPC_HOSTILE_1]:
            n.step(f"{npc_id} KNOWS_ABOUT event", api_post(http_client, f"{graph}/edges/KNOWS_ABOUT", {
                "src_id": npc_id, "dst_id": EVENT_ID,
                "properties": {"knowledge_state": "knows", "learned_at_tick": 1},
            }))

        n.narrate("Two gossip ticks run. Expect allied NPCs to share freely; hostile pairs to distort or withhold.")

        for tick in [1, 2]:
            n.step(f"Gossip tick {tick}", api_post(http_client, f"{admin}/batch/gossip_tick", {
                "tick_override": 1000 + tick, "max_pairs": 10,
            }))

    finally:
        n.save()
