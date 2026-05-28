"""
Module: seed_village_world
Layer: seeds/worlds (external client)
Purpose: Seed the village eval world via the NPC Engine HTTP API. Idempotent on re-run.
Dependencies: demo_game.client
Used by: make seed-village-world, python seeds/worlds/seed_village_world.py

World prefix: vw_
World theme: rural village, crop blight, bandits, missing child — no war or military context.
Intended use: eval cases that require independent non-demo NPCs (vw_elder, vw_guard,
vw_healer, vw_farmer, vw_fence) and village events (blight, raid, missing child).

Run from repo root so demo_game is importable:
    python seeds/worlds/seed_village_world.py [--base-url http://localhost:8000]
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from demo_game.client import EngineClient

logger = logging.getLogger(__name__)

_GAME_TIME: dict = {"year": 1, "season": "autumn", "day": 3, "time_of_day": "morning"}
_WORLD_STATE_ID = "world"


# ---------------------------------------------------------------------------
# Builder functions (copied from seeds/worlds/seed_demo_world.py — keep in sync)
# ---------------------------------------------------------------------------


def build_location_payload(
    id: str,
    name: str,
    location_tag: str,
    descriptor: str,
) -> dict:
    now = _now()
    return {
        "id": id,
        "name": name,
        "location_tag": location_tag,
        "descriptor": descriptor,
        "region": "village",
        "last_graph_updated_at": now,
    }


def build_faction_payload(
    id: str,
    name: str,
    archetype: str,
    description: str,
) -> dict:
    now = _now()
    return {
        "id": id,
        "name": name,
        "archetype": archetype,
        "description": description,
        "is_active": True,
        "created_at": now,
        "last_graph_updated_at": now,
    }


def build_npc_payload(
    id: str,
    name: str,
    archetype: str,
    faction_id: str,
    location_id: str,
    biography: str,
    gossipy: int,
    credulity: int,
    honesty: int,
    voice_descriptor: str | None = None,
) -> dict:
    now = _now()
    return {
        "id": id,
        "name": name,
        "archetype": archetype,
        "faction": faction_id,
        "biography": biography,
        "is_player": False,
        "is_active": True,
        "gossipy": gossipy,
        "credulity": credulity,
        "honesty": honesty,
        "current_mood": "neutral",
        "voice_descriptor": voice_descriptor,
        "created_at": now,
        "updated_at": now,
        "last_graph_updated_at": now,
    }


def build_world_state_payload(
    epoch: str,
    active_conditions: list[str],
) -> dict:
    """Return a world_state node property dict.

    Args:
        epoch: Current epoch name (e.g. "age_of_peace", "war").
        active_conditions: List of active condition IDs.

    Returns:
        Dict with all required world_state properties.
    """
    now = _now()
    return {
        "id": _WORLD_STATE_ID,
        "epoch": epoch,
        "active_conditions": active_conditions,
        "faction_standings": {},
        "time_of_day": "morning",
        "weather": "clear",
        "last_updated_at": now,
        "last_graph_updated_at": now,
    }


def build_event_payload(
    id: str,
    summary: str,
    event_type: str,
    location_id: str,
    severity: int,
    is_public: bool = False,
    tick_id: int = 0,
) -> dict:
    now = _now()
    return {
        "id": id,
        "summary": summary,
        "event_type": event_type,
        "location_id": location_id,
        "severity": severity,
        "is_public": is_public,
        "tick_id": tick_id,
        "occurred_at": now,
        "last_graph_updated_at": now,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_node(client: EngineClient, node_type: str, payload: dict) -> str:
    if client.get_node(node_type, payload["id"]) is not None:
        logger.info("  skip %s/%s (exists)", node_type, payload["id"])
        return "skipped"
    client.upsert_node(node_type, payload)
    logger.info("  created %s/%s", node_type, payload["id"])
    return "created"


def _seed_edge(
    client: EngineClient,
    edge_type: str,
    src_id: str,
    dst_id: str,
    properties: dict | None = None,
) -> str:
    client.upsert_edge(edge_type, src_id, dst_id, properties)
    logger.info("  upserted edge %s %s→%s", edge_type, src_id, dst_id)
    return "created"


def _seed_npc_inner_life(
    client: EngineClient,
    npc_id: str,
    beliefs: list[tuple[str, int]],
    goals: list[tuple[str, int]],
    memories: list[tuple[str, int, int]],
    secret: tuple[str, int],
) -> int:
    if client.get_beliefs(npc_id):
        logger.info("  skip inner life for %s (already seeded)", npc_id)
        return 0

    created = 0
    for content, confidence in beliefs:
        client.post_belief(npc_id, content, confidence, _GAME_TIME)
        created += 1
    for description, urgency in goals:
        client.post_goal(npc_id, description, urgency, _GAME_TIME)
        created += 1
    for content, vividness, emotional_charge in memories:
        client.post_memory(npc_id, content, vividness, emotional_charge, _GAME_TIME)
        created += 1
    content, severity = secret
    client.post_secret(npc_id, content, severity, _GAME_TIME)
    created += 1
    logger.info("  created %d inner-life items for %s", created, npc_id)
    return created


# ---------------------------------------------------------------------------
# Village world data (vw_ prefix)
# ---------------------------------------------------------------------------

_LOCATIONS = [
    ("vw_village_square", "Village Square", "square", "The open heart of the village where news travels fastest."),
    ("vw_gate", "Village Gate", "gate", "The single road in and out, watched by a nervous young guard."),
    ("vw_healer_hut", "Healer's Hut", "workshop", "A cluttered hut smelling of dried herbs and woodsmoke."),
    ("vw_farmland", "South Fields", "farmland", "The main crop fields south of the village, now showing signs of blight."),
]

_FACTIONS = [
    ("vw_village_council", "Village Council", "civic", "The governing body of village elders responsible for local order and decisions."),
    ("vw_farmers", "Farmers Collective", "agrarian", "A loose cooperative of farming families who share seed, labour, and grievances."),
]

_NPCS = [
    # (id, name, archetype, faction_id, location_id, biography, gossipy, credulity, honesty, voice_descriptor)
    ("vw_healer", "Maret", "healer", "neutral", "vw_healer_hut",
     "The village healer — calm, precise, and deeply worried about the spreading blight.", 40, 65, 85,
     "Quiet and careful. Weighs words like ingredients — uses the right amount, no more."
     " Asks diagnostic questions. Shows concern through precision, not warmth."),
    ("vw_elder", "Aldwin", "elder", "vw_village_council", "vw_village_square",
     "The eldest member of the council, slow to speak and slower to act, but rarely wrong.", 55, 70, 90,
     "Formal, slow cadence. Speaks as if each sentence might be recorded."
     " References past decisions and village precedent. Reluctant to speculate."),
    ("vw_farmer", "Jorin", "farmer", "vw_farmers", "vw_farmland",
     "A blunt, weather-beaten farmer who trusts the sky more than any man's word.", 50, 60, 75,
     "Blunt. Names problems without decoration. Short sentences."
     " Asks practical questions about practical things. Skeptical of authority but not of hard evidence."),
    ("vw_guard", "Bren", "guard", "vw_village_council", "vw_gate",
     "A nervous young guard who follows every rule he was given and quietly regrets some of them.", 30, 45, 80,
     "Terse and watchful. Answers questions with the minimum required."
     " Asks for credentials by habit. Mentions procedure."),
    ("vw_fence", "Silon", "peddler", "neutral", "vw_gate",
     "A travelling peddler who speaks in half-truths and always seems to be passing through.", 70, 40, 25,
     "Evasive by reflex. Redirects, qualifies, hedges. Uses 'apparently', 'I'm told', 'word is'."
     " Never admits direct knowledge of anything illegal."),
]

_NPC_MEMBER_OF = [
    ("vw_elder", "vw_village_council", "officer"),
    ("vw_guard", "vw_village_council", "member"),
    ("vw_farmer", "vw_farmers", "member"),
]

_NPC_INNER_LIFE: dict[str, dict] = {
    "vw_healer": {
        "beliefs": [
            ("Blight spreads faster than people admit — by the time you see it on the leaves, it is already in the roots.", 85),
            ("Children go missing near the forest because adults stop teaching respect for it.", 70),
        ],
        "goals": [
            ("Find an effective treatment for the blight before it reaches the northern fields.", 90),
        ],
        "memories": [
            ("The summer I lost three patients in a week to a fever no herb could touch — I rewrote everything I thought I knew.", 92, -80),
            ("The child I helped bring into the world who is now missing — I know her mother.", 88, -65),
        ],
        "secret": ("She suspects the blight may have started on one particular farm but lacks proof to accuse them.", 75),
    },
    "vw_elder": {
        "beliefs": [
            ("Bandits do not raid at random — someone local told them which farm was undefended.", 80),
            ("Every crisis this village has survived began as a small problem someone thought too minor to mention.", 85),
        ],
        "goals": [
            ("Prevent panic about the blight from fracturing the village council before the harvest is in.", 70),
        ],
        "memories": [
            ("The last time bandits came, twenty years ago — we lost the mill and three men before it was over.", 90, -80),
            ("The founding of the council — I was the youngest man at the table and the only one still living who remembers it.", 92, 75),
        ],
        "secret": ("He knew the blight was spreading weeks before the public announcement — he delayed to prevent panic.", 80),
    },
    "vw_farmer": {
        "beliefs": [
            ("Rain does not lie and coin does — I trust the sky more than the market.", 75),
            ("Outsiders always arrive with their problems and leave with our resources.", 70),
        ],
        "goals": [
            ("Get the south field quarantined before the blight reaches the grain store.", 85),
        ],
        "memories": [
            ("The drought three seasons back that cost half my yield — I am still paying off that debt.", 88, -75),
            ("The morning I found the first black patch on the wheat — I thought I was imagining it.", 80, -60),
        ],
        "secret": ("He borrowed money from the peddler at terms he cannot repay without a full harvest.", 65),
    },
    "vw_guard": {
        "beliefs": [
            ("The bandits will come back — they always return when a village looks vulnerable.", 80),
            ("The elder knows more about this blight than he is telling the rest of us.", 55),
        ],
        "goals": [
            ("Organise a proper watch rotation before the next raid attempt.", 75),
        ],
        "memories": [
            ("The night of the bandit raid — I was at the wrong end of the village and heard the shouting too late to help anyone.", 90, -70),
            ("The day the elder appointed me guard — I was so proud I forgot to ask what the job actually required.", 75, 55),
        ],
        "secret": ("He fell asleep at his post the night of the bandit raid.", 85),
    },
    "vw_fence": {
        "beliefs": [
            ("Everyone has something to trade if you know the right currency.", 80),
            ("Village elders always know about the crime — they just need the right inducement to look away.", 65),
        ],
        "goals": [
            ("Move the goods acquired after the raid through the village quickly before anyone asks the right questions.", 90),
        ],
        "memories": [
            ("The constable who let me go for a share of the take — that was the first lesson in how the world actually works.", 85, 60),
            ("The time I stayed too long in a village and had to flee at dawn with half my stock and no boots.", 80, -55),
        ],
        "secret": ("He is fencing items stolen from the very villagers who let him sleep under their roof.", 90),
    },
}

_EVENTS = [
    # (id, summary, event_type, location_id, severity, is_public)
    ("vw_crop_blight", "A fungal blight is spreading through the south fields", "disaster", "vw_farmland", 65, True),
    ("vw_bandit_raid", "Bandits struck a farmstead two nights ago and made off with livestock and stored grain", "conflict", "vw_gate", 70, False),
    ("vw_missing_child", "A young girl vanished near the forest edge three days ago", "mystery", "vw_village_square", 80, True),
]

# KNOWS_ABOUT: (npc_id, event_id, knowledge_state, distortion_type, distortion_level, distorted_summary)
_KNOWS_ABOUT = [
    ("vw_elder", "vw_crop_blight",
     "fact", None, 0,
     "The blight is real and it is spreading. I have seen the field reports myself. We must act before the harvest."),
    ("vw_guard", "vw_bandit_raid",
     "rumor", "minimization", 30,
     "Word is a farm to the east got hit, but I only heard it second-hand. Could be worse than they're saying, or better."),
    ("vw_healer", "vw_missing_child",
     "witnessed", None, 0,
     "I spoke with the mother that morning. The girl left for the mill at first light and never arrived. I saw her on the road myself not an hour before."),
]

_NPC_LOCATED_AT = [
    ("vw_healer", "vw_healer_hut"),
    ("vw_elder", "vw_village_square"),
    ("vw_farmer", "vw_farmland"),
    ("vw_guard", "vw_gate"),
    ("vw_fence", "vw_gate"),
]


# ---------------------------------------------------------------------------
# seed_all
# ---------------------------------------------------------------------------


def seed_all(client: EngineClient) -> dict:
    """Seed the village eval world via the NPC Engine HTTP API.

    Dependency order:
    1. Locations
    2. Factions
    3. Characters
    4. MEMBER_OF edges
    5. NPC inner life
    6. Events
    7. KNOWS_ABOUT edges
    8. LOCATED_AT edges

    Returns:
        Summary dict with "created" and "skipped" integer counts.
    """
    created = 0
    skipped = 0

    def _tally(result: str) -> None:
        nonlocal created, skipped
        if result == "created":
            created += 1
        else:
            skipped += 1

    logger.info("[seed-village] Locations")
    for loc_id, name, tag, descriptor in _LOCATIONS:
        _tally(_seed_node(client, "Location", build_location_payload(loc_id, name, tag, descriptor)))

    logger.info("[seed-village] Factions")
    for faction_id, name, archetype, description in _FACTIONS:
        _tally(_seed_node(client, "Faction", build_faction_payload(faction_id, name, archetype, description)))

    logger.info("[seed-village] Characters")
    for npc_id, name, archetype, faction_id, location_id, biography, gossipy, credulity, honesty, voice_descriptor in _NPCS:
        _tally(_seed_node(
            client,
            "Character",
            build_npc_payload(npc_id, name, archetype, faction_id, location_id, biography, gossipy, credulity, honesty, voice_descriptor),
        ))

    logger.info("[seed-village] MEMBER_OF edges")
    for npc_id, faction_id, role in _NPC_MEMBER_OF:
        _tally(_seed_edge(client, "MEMBER_OF", npc_id, faction_id, {
            "role": role,
            "status": "active",
            "joined_at": _now(),
        }))

    logger.info("[seed-village] NPC inner life")
    for npc_id, life in _NPC_INNER_LIFE.items():
        n = _seed_npc_inner_life(
            client,
            npc_id,
            beliefs=life["beliefs"],
            goals=life["goals"],
            memories=life["memories"],
            secret=life["secret"],
        )
        created += n
        if n == 0:
            skipped += len(life["beliefs"]) + len(life["goals"]) + len(life["memories"]) + 1

    logger.info("[seed-village] Events")
    for evt_id, summary, event_type, location_id, severity, is_public in _EVENTS:
        _tally(_seed_node(
            client,
            "Event",
            build_event_payload(
                id=evt_id,
                summary=summary,
                event_type=event_type,
                location_id=location_id,
                severity=severity,
                is_public=is_public,
            ),
        ))

    logger.info("[seed-village] world_state")
    # Always upsert world_state (not skip-if-exists) so active_conditions are
    # set correctly regardless of prior seed runs. Uses id="world" to match
    # the context builder's default world_id.
    client.upsert_node("world_state", build_world_state_payload(
        "age_of_peace",
        ["crop_blight"],
    ))
    created += 1
    logger.info("  upserted world_state/world")

    logger.info("[seed-village] KNOWS_ABOUT edges")
    for npc_id, event_id, knowledge_state, distortion_type, distortion_level, distorted_summary in _KNOWS_ABOUT:
        _tally(_seed_edge(client, "KNOWS_ABOUT", npc_id, event_id, {
            "knowledge_state": knowledge_state,
            "distortion_type": distortion_type,
            "distortion_level": distortion_level,
            "distorted_summary": distorted_summary,
            "learned_at_tick": 0,
            "source_character_id": None,
        }))

    logger.info("[seed-village] LOCATED_AT edges")
    for npc_id, loc_id in _NPC_LOCATED_AT:
        _tally(_seed_edge(client, "LOCATED_AT", npc_id, loc_id, {
            "is_permanent_resident": True,
            "arrived_at": _now(),
        }))

    logger.info("[seed-village] Done — created=%d skipped=%d", created, skipped)
    return {"created": created, "skipped": skipped}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse
    import os

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Seed the village eval world via the NPC Engine HTTP API.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("NPC_BASE_URL", "http://localhost:8000"),
        help="NPC Engine base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("API_KEY_SECRET", "eval-key-change-me"),
        help="Bearer token (default: eval-key-change-me or API_KEY_SECRET env var)",
    )
    args = parser.parse_args()

    from demo_game.client import EngineClient

    client = EngineClient(args.base_url, args.api_key)
    try:
        result = seed_all(client)
        print(f"Village world seed complete — created={result['created']} skipped={result['skipped']}")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
