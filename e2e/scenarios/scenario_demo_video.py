"""
Module: scenario_demo_video
Layer: e2e
Purpose: Self-contained 90-second demo scenario for video voiceover.
Dependencies: conftest fixtures, NPC Engine HTTP API.
Used by: pytest --scenarios-only, make demo-video.

Story arc:
  SETUP — The Iron Lantern tavern is created. Two NPCs take their places:
    Mira, the innkeeper who hears everything, and Gareth, a wanderer
    passing through. A travelling merchant has just told Mira terrifying
    news from the eastern road.

  ACT 1 — Mira alone knows about the plague sighting. A gossip tick fires;
    Gareth may overhear — but tavern whispers distort easily.

  ACT 2 — The player sits down with Mira. She tells what she knows,
    straight from the merchant's mouth.

  ACT 3 — The player finds Gareth by the hearth. He's heard something —
    but the version has changed in the retelling.

Cleanup: all demo-created nodes are removed in the finally block.

Marks:
  @pytest.mark.demo_video — run alone with `make demo-video`
"""

from __future__ import annotations

import textwrap
from datetime import datetime, timezone

import httpx
import pytest

from conftest import Narrator, api_get, api_post, api_put, char_props, loc_props

SCENARIO_ID = "scenario_demo_video"
_WIDTH = 64

# ── Stable IDs (prefixed to avoid collision with seed data) ──────────────────

LOC_TAVERN = "loc_dv_iron_lantern"
FAC_INNKEEPERS = "fac_dv_innkeepers_guild"
FAC_WANDERERS = "fac_dv_wanderers_guild"
NPC_MIRA = "npc_dv_mira"
NPC_GARETH = "npc_dv_gareth"
PLAYER = "player_dv_traveller"
EVENT_PLAGUE = "evt_dv_plague_sighting"


# ── Voiceover helpers ────────────────────────────────────────────────────────


def _voiceover(n: Narrator, lines: list[str]) -> None:
    """Print multi-line voiceover text as a single narration block."""
    text = " ".join(line.strip() for line in lines)
    n.narrate(text)


def _dialogue_line(speaker: str, reply: str) -> None:
    """Print a single NPC speech line in transcript style."""
    wrapped = textwrap.fill(
        reply.strip(),
        width=_WIDTH - 4,
        initial_indent="    ",
        subsequent_indent="    ",
    )
    print(f"\n  [{speaker}]")
    print(wrapped[:800])
    print()


# ── Scenario ─────────────────────────────────────────────────────────────────


@pytest.mark.demo_video
def test_demo_video_scenario(http_client: httpx.Client) -> None:
    """Run the 90-second video demo scenario end-to-end.

    Creates a tavern world, seeds a plague-sighting event, propagates
    it via gossip, then asks both NPCs what they know via dialogue.
    All created nodes are removed in the finally block.
    """
    n = Narrator(SCENARIO_ID)
    now = datetime.now(timezone.utc).isoformat()
    admin = "/v1/admin"
    graph = "/v1/graph"

    created_chars: list[str] = []
    created_event: str | None = None
    created_location: str | None = None

    try:
        # ══════════════════════════════════════════════════════════════════
        # SETUP — Build the world
        # ══════════════════════════════════════════════════════════════════

        _voiceover(n, [
            "The Iron Lantern. A roadside tavern at the edge of the eastern trade route.",
            "Mira has run this place for twenty years.",
            "Gareth arrived at dusk, asking only for ale and a dry place to sleep.",
            "Neither of them knows yet that the news coming down the road will change everything.",
        ])

        # Location
        resp = n.step("Create tavern location", api_post(http_client, f"{graph}/nodes/Location", {
            "properties": loc_props(
                LOC_TAVERN,
                "The Iron Lantern",
                location_tag="tavern",
                region="Eastern Road",
                descriptor=(
                    "A low-ceilinged tavern with smoke-stained beams and a fire "
                    "that has not gone out in twenty years."
                ),
                now=now,
            ),
        }))
        assert resp["status"] == 200, f"Failed to create tavern: {resp}"
        created_location = LOC_TAVERN

        # Factions
        n.step("Create Innkeepers Guild", api_post(http_client, f"{admin}/factions/", {
            "id": FAC_INNKEEPERS,
            "name": "Innkeepers Guild",
            "archetype": "merchant",
            "is_active": True,
        }))
        n.step("Create Guild of Wanderers", api_post(http_client, f"{admin}/factions/", {
            "id": FAC_WANDERERS,
            "name": "Guild of Wanderers",
            "archetype": "adventurer",
            "is_active": True,
        }))

        # Neutral standing between factions (50 = neither allies nor enemies)
        n.step("Set faction standing: Innkeepers → Wanderers (neutral)",
               api_put(http_client, f"{admin}/factions/{FAC_INNKEEPERS}/standings/{FAC_WANDERERS}",
                       {"standing": 50}))
        n.step("Set faction standing: Wanderers → Innkeepers (neutral)",
               api_put(http_client, f"{admin}/factions/{FAC_WANDERERS}/standings/{FAC_INNKEEPERS}",
                       {"standing": 50}))

        # NPCs
        resp = n.step("Create Mira (innkeeper)", api_post(http_client, f"{graph}/nodes/Character", {
            "properties": char_props(
                NPC_MIRA,
                "Mira",
                is_player=False,
                archetype="innkeeper",
                biography=(
                    "Mira has kept the Iron Lantern for two decades. "
                    "She hears everything and forgets nothing. "
                    "Her loyalty is to the road and the people who travel it."
                ),
                gossipy=75,
                credulity=60,
                honesty=85,
                now=now,
            ),
        }))
        assert resp["status"] == 200, f"Failed to create Mira: {resp}"
        created_chars.append(NPC_MIRA)

        resp = n.step("Create Gareth (wanderer)", api_post(http_client, f"{graph}/nodes/Character", {
            "properties": char_props(
                NPC_GARETH,
                "Gareth",
                is_player=False,
                archetype="wanderer",
                biography=(
                    "Gareth has been walking the eastern trade routes for three years. "
                    "He trusts rumor more than record, and embellishes freely when retelling stories."
                ),
                gossipy=85,
                credulity=80,
                honesty=45,
                now=now,
            ),
        }))
        assert resp["status"] == 200, f"Failed to create Gareth: {resp}"
        created_chars.append(NPC_GARETH)

        # Player
        resp = n.step("Create player (traveller)", api_post(http_client, f"{graph}/nodes/Character", {
            "properties": char_props(
                PLAYER,
                "The Traveller",
                is_player=True,
                archetype="adventurer",
                biography="A traveller passing through on the eastern road.",
                now=now,
            ),
        }))
        assert resp["status"] == 200, f"Failed to create player: {resp}"
        created_chars.append(PLAYER)

        # Place everyone at the tavern
        for char_id in [NPC_MIRA, NPC_GARETH, PLAYER]:
            n.step(f"{char_id} LOCATED_AT tavern", api_post(http_client, f"{graph}/edges/LOCATED_AT", {
                "src_id": char_id,
                "dst_id": LOC_TAVERN,
                "properties": {"is_permanent_resident": char_id == NPC_MIRA, "arrived_at": now},
            }))

        # Faction membership
        n.step("Mira joins Innkeepers Guild", api_post(http_client, f"{admin}/factions/{FAC_INNKEEPERS}/members", {
            "character_id": NPC_MIRA,
            "role": "member",
            "status": "active",
        }))
        n.step("Gareth joins Guild of Wanderers", api_post(http_client, f"{admin}/factions/{FAC_WANDERERS}/members", {
            "character_id": NPC_GARETH,
            "role": "member",
            "status": "active",
        }))

        # ══════════════════════════════════════════════════════════════════
        # ACT 1 — The plague sighting arrives
        # ══════════════════════════════════════════════════════════════════

        _voiceover(n, [
            "A merchant stumbles through the door just before nightfall.",
            "His cart horse is dead on the road.",
            "He tells Mira what he saw: livestock rotting in the fields,",
            "travelers turning back, the eastern villages gone quiet.",
            "The plague has reached the border.",
        ])

        resp = n.step("Seed plague-sighting event", api_post(http_client, f"{graph}/nodes/Event", {
            "properties": {
                "id": EVENT_PLAGUE,
                "summary": (
                    "A merchant reported dead livestock along the eastern road near the border villages. "
                    "Travelers are turning back. Locals believe the plague has reached the frontier."
                ),
                "severity": 82,
                "location_id": LOC_TAVERN,
                "occurred_at": now,
                "tick_id": 1,
                "event_type": "disaster",
                "is_public": False,
                "last_graph_updated_at": now,
            },
        }))
        assert resp["status"] == 200, f"Failed to create event: {resp}"
        created_event = EVENT_PLAGUE

        # Mira is the only direct witness
        n.step("Mira KNOWS_ABOUT the plague sighting", api_post(http_client, f"{graph}/edges/KNOWS_ABOUT", {
            "src_id": NPC_MIRA,
            "dst_id": EVENT_PLAGUE,
            "properties": {"knowledge_state": "knows", "learned_at_tick": 1},
        }))

        _voiceover(n, [
            "Gareth is at the other end of the bar, nursing his ale.",
            "He didn't hear the merchant directly.",
            "But taverns have thin walls.",
        ])

        # Gossip tick — Mira may tell Gareth, with possible distortion
        n.step("Gossip tick fires (Mira → Gareth?)", api_post(http_client, f"{admin}/batch/gossip_tick", {
            "tick_override": 2,
            "max_pairs": 20,
        }))

        # Check what Gareth knows after gossip
        gareth_state = n.step("Gareth's knowledge state (after gossip)", api_get(
            http_client, f"/v1/npc/{NPC_GARETH}/state"
        ))

        gareth_events = (
            (gareth_state.get("body") or {})
            .get("known_events", [])
        )
        if gareth_events:
            n.narrate("Gareth has heard something. The question is — what version?")
        else:
            n.narrate(
                "The gossip didn't reach Gareth this tick. "
                "He'll stay in the dark — for now."
            )

        # ══════════════════════════════════════════════════════════════════
        # ACT 2 — Player speaks to Mira
        # ══════════════════════════════════════════════════════════════════

        _voiceover(n, [
            "You take a stool at the bar and ask Mira what she's heard.",
            "She sets down the cup she was drying and looks at you.",
        ])

        mira_turn = n.step(
            "Player asks Mira about news from the east",
            api_post(http_client, "/v1/dialogue", {
                "player_id": PLAYER,
                "npc_id": NPC_MIRA,
                "player_message": "What news from the eastern road? The merchant who came in — he looked shaken.",
                "location_id": LOC_TAVERN,
                "session_id": f"{SCENARIO_ID}:mira_turn1",
            }),
        )

        mira_reply = (mira_turn.get("body") or {}).get("npc_response", "")
        if mira_reply:
            _dialogue_line("Mira", mira_reply)
            assert len(mira_reply) > 20, "Mira's response was suspiciously short"
        else:
            n.narrate("(Mira is silent — LLM backend may be unavailable)")

        # ══════════════════════════════════════════════════════════════════
        # ACT 3 — Player speaks to Gareth
        # ══════════════════════════════════════════════════════════════════

        _voiceover(n, [
            "You find Gareth by the hearth, staring into the fire.",
            "Wanderers always know something.",
            "The question is whether what they know is still true.",
        ])

        gareth_turn = n.step(
            "Player asks Gareth about news from the east",
            api_post(http_client, "/v1/dialogue", {
                "player_id": PLAYER,
                "npc_id": NPC_GARETH,
                "player_message": "You've been on the road. What are people saying about the east?",
                "location_id": LOC_TAVERN,
                "session_id": f"{SCENARIO_ID}:gareth_turn1",
            }),
        )

        gareth_reply = (gareth_turn.get("body") or {}).get("npc_response", "")
        if gareth_reply:
            _dialogue_line("Gareth", gareth_reply)
            assert len(gareth_reply) > 20, "Gareth's response was suspiciously short"
        else:
            n.narrate("(Gareth is silent — LLM backend may be unavailable)")

        # ── Narrative close ───────────────────────────────────────────────

        _voiceover(n, [
            "Same event. Two people. Two versions of the truth.",
            "This is how the world works in the NPC Engine.",
            "Knowledge flows. Memory distorts. Every NPC carries their own version of events.",
            "The world remembers — even when the truth changes in the telling.",
        ])

        print(f"\n{'═' * _WIDTH}")
        print("  [PASS] scenario_demo_video completed.")
        print(f"{'═' * _WIDTH}\n")

    finally:
        # Delete characters and location (factions are benign artifacts)
        for char_id in created_chars:
            http_client.delete(f"{admin}/graph/characters/{char_id}")
        if created_event:
            http_client.delete(f"{admin}/graph/events/{created_event}")
        if created_location:
            http_client.delete(f"{admin}/graph/locations/{created_location}")
        n.save("_demo_video")
