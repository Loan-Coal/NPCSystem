"""
Module: seed_npc_data
Layer: demo_game (external client)
Purpose: Data-only module containing NPC definitions for the expanded Munich demo world.
         Imported by seed.py to keep the seeder under the 300-line limit.
         Contains the H2.2 six new NPCs (bren_smith, nessa_priestess, dorn_dockmaster,
         vex_spymaster, tilda_herbalist, garrick_deserter) with their inner-life data.
Dependencies: demo_game.constants (for stable ID constants only)
Used by: demo_game.seed
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# H2.2 new NPC stable ID constants
# ---------------------------------------------------------------------------

NPC_ID_BREN_SMITH: str = "bren_smith"
NPC_ID_NESSA_PRIESTESS: str = "nessa_priestess"
NPC_ID_DORN_DOCKMASTER: str = "dorn_dockmaster"
NPC_ID_VEX_SPYMASTER: str = "vex_spymaster"
NPC_ID_TILDA_HERBALIST: str = "tilda_herbalist"
NPC_ID_GARRICK_DESERTER: str = "garrick_deserter"

# ---------------------------------------------------------------------------
# H2.3 new location stable ID constants
# ---------------------------------------------------------------------------

LOC_ID_FORGE: str = "loc_forge"
LOC_ID_TEMPLE: str = "loc_temple"
LOC_ID_DOCKS: str = "loc_docks"
LOC_ID_NORTH_GATE: str = "loc_north_gate"

# District (tier-1) location IDs
LOC_ID_OLD_QUARTER: str = "loc_old_quarter"
LOC_ID_HARBOR_DISTRICT: str = "loc_harbor_district"

# ---------------------------------------------------------------------------
# H2.4 new faction stable ID constants
# ---------------------------------------------------------------------------

FACTION_ID_CROWN_LOYALISTS: str = "crown_loyalists"
FACTION_ID_DOCKSIDE_SMUGGLERS: str = "dockside_smugglers"

# ---------------------------------------------------------------------------
# H2.2 NPC tuples:
# (id, name, archetype, faction_id, location_id, biography,
#  gossipy, credulity, honesty, voice_descriptor)
# ---------------------------------------------------------------------------

H2_NPCS: list[tuple] = [
    (
        NPC_ID_BREN_SMITH,
        "Bren",
        "blacksmith",
        "city_guard",
        LOC_ID_FORGE,
        "Supplies the guard with arms and repairs; resents every tithe they skim from his forge.",
        35, 45, 70,
        "Gruff and straightforward. Every complaint is delivered as a statement of fact."
        " Loyal to the guard grudgingly — the contract feeds him, but the tithes sting."
        " Does not embellish; does not speculate.",
    ),
    (
        NPC_ID_NESSA_PRIESTESS,
        "Nessa",
        "priestess",
        "neutral",
        LOC_ID_TEMPLE,
        "The moral counterweight of the city; hears confessions from every faction and holds them all.",
        40, 60, 85,
        "Composed and unhurried. Asks questions more than she answers them."
        " Speaks in measured phrases, never raising her voice."
        " Treats every secret as a burden she accepts willingly.",
    ),
    (
        NPC_ID_DORN_DOCKMASTER,
        "Dorn",
        "dockmaster",
        "merchants_guild",
        LOC_ID_DOCKS,
        "Controls the loading manifests; every off-book shipment passes through his ledger — or doesn't.",
        55, 40, 35,
        "Businesslike and evasive in equal measure. Quotes prices before he quotes opinions."
        " Pauses before sensitive answers, as though recalculating risk."
        " Claims everything is above board; means none of it.",
    ),
    (
        NPC_ID_VEX_SPYMASTER,
        "Vex",
        "spymaster",
        FACTION_ID_CROWN_LOYALISTS,
        "loc_guard_barracks",
        "The crown's eyes in the city; brokers treaties and oaths on behalf of a king most have forgotten.",
        20, 30, 40,
        "Precise and economical. Each word is selected; none are wasted."
        " Implies more than he states. Asks clarifying questions as a form of pressure."
        " Never reveals how much he already knows.",
    ),
    (
        NPC_ID_TILDA_HERBALIST,
        "Tilda",
        "herbalist",
        "thieves_guild",
        "loc_market_square",
        "Sells remedies at market — and something stronger to those who know how to ask.",
        60, 50, 45,
        "Cheerful on the surface; careful underneath. Uses botanical metaphors as deflection."
        " Generous with common remedies, tight with rare ones."
        " Never admits a customer's true purpose; that would be rude.",
    ),
    (
        NPC_ID_GARRICK_DESERTER,
        "Garrick",
        "deserter",
        "neutral",
        "loc_tavern",
        "A soldier who walked away from the Iron Legion's advance; hiding in plain sight behind a cup.",
        30, 65, 55,
        "Quiet and watchful. Keeps his back to the wall and his answers short."
        " Changes the subject when the war comes up. Laughs too quickly when nervous."
        " War made him personal — every casualty has a name in his head.",
    ),
]

# ---------------------------------------------------------------------------
# H2.2 NPC MEMBER_OF entries (new NPCs' faction membership roles)
# ---------------------------------------------------------------------------

H2_NPC_MEMBER_OF: list[tuple] = [
    (NPC_ID_BREN_SMITH, "city_guard", "contractor"),
    (NPC_ID_DORN_DOCKMASTER, "merchants_guild", "officer"),
    (NPC_ID_VEX_SPYMASTER, FACTION_ID_CROWN_LOYALISTS, "officer"),
    (NPC_ID_TILDA_HERBALIST, "thieves_guild", "associate"),
]

# ---------------------------------------------------------------------------
# H2.2 NPC inner life (beliefs, goals, memories, secret)
# ---------------------------------------------------------------------------

H2_NPC_INNER_LIFE: dict[str, dict] = {
    NPC_ID_BREN_SMITH: {
        "beliefs": [
            ("The guard takes a third of my contract pay as 'protection' — protection from themselves.", 80),
            ("A city that cannot arm its own soldiers is a city already lost.", 75),
        ],
        "goals": [
            ("Renegotiate the forge contract before the war pushes iron prices beyond what the guard will pay.", 65),
        ],
        "memories": [
            ("The morning the guard captain walked in and increased the tithe. He did not ask.", 85, -70),
            ("Forging the sword that the last guard captain wore to his death. I wondered if the blade held.", 70, 40),
        ],
        "secret": ("He has been shaving the steel alloy ratios for six months — the guard's new swords are weaker than reported.", 75),
    },
    NPC_ID_NESSA_PRIESTESS: {
        "beliefs": [
            ("Every faction claims righteousness. None of them has sat with the dying to test that claim.", 85),
            ("Confession is not absolution — but it is the only honest accounting most people ever give.", 70),
        ],
        "goals": [
            ("Keep the temple neutral so the wounded from both sides can be brought here without fear.", 80),
        ],
        "memories": [
            ("The night a guild enforcer and a city guard both bled on the same floor and refused to look at each other.", 90, -60),
            ("A merchant who confessed to arson and went home lighter. I lit a candle for those who lost the warehouse.", 78, 45),
        ],
        "secret": ("She knows who set the market fire and has not told the guard — the confession was genuine.", 80),
    },
    NPC_ID_DORN_DOCKMASTER: {
        "beliefs": [
            ("The manifest is a fiction — the real ledger lives in my head and nowhere else.", 75),
            ("Lira moves more product through this port than the merchants guild does. That is a fact worth knowing.", 80),
        ],
        "goals": [
            ("Keep the smuggling routes open long enough to make one last large shipment before the war closes the docks.", 70),
        ],
        "memories": [
            ("The night I let a crate of stolen guard armor through without inspecting it. Lira paid triple the usual.", 82, 55),
            ("The morning the harbour authority showed up unannounced. I had the false manifests ready in thirty seconds.", 88, 30),
        ],
        "secret": ("He has been running the smuggling operation that Lira fronts — she thinks she runs it; she does not.", 85),
    },
    NPC_ID_VEX_SPYMASTER: {
        "beliefs": [
            ("The city's factions are negotiating with each other every day. Most of them do not realize it.", 90),
            ("A signed treaty is worth nothing without leverage behind it — the crown learned that the hard way.", 85),
        ],
        "goals": [
            ("Broker a non-aggression accord between the city guard and the merchants before the Iron Legion makes it irrelevant.", 75),
        ],
        "memories": [
            ("Watching a peace negotiation collapse over a single clause no one would reword. Both sides lost more than they would have given.", 88, -65),
            ("The day I was assigned to this city — a posting no one else wanted. I have been here long enough to know why.", 72, 30),
        ],
        "secret": ("He reports to the crown but has stopped forwarding certain intelligence — enough to make himself indispensable to both sides.", 90),
    },
    NPC_ID_TILDA_HERBALIST: {
        "beliefs": [
            ("Plants do not lie. People always do. That is why I prefer plants.", 75),
            ("The guild asked me to poison someone once. I said no. They have not asked again.", 70),
        ],
        "goals": [
            ("Find a reliable supply of northwood bark before the war cuts the trade routes — it is the only analgesic that works.", 65),
        ],
        "memories": [
            ("The day a guild contact brought me a herb I had never seen. I grew it; I sold what it produced quietly.", 80, 50),
            ("Treating a city guard's wound after a market brawl. He paid in coin and never asked what was in the poultice.", 72, 35),
        ],
        "secret": ("She has a cultivated batch of a controlled herb that the guild does not know about — her private insurance.", 70),
    },
    NPC_ID_GARRICK_DESERTER: {
        "beliefs": [
            ("The Iron Legion does not take prisoners. I walked away because I saw what they do to towns that resist.", 90),
            ("Everyone in this city is going to find out what the war really looks like. I already know.", 80),
        ],
        "goals": [
            ("Stay alive and invisible long enough to decide whether to warn the city or simply leave it.", 55),
        ],
        "memories": [
            ("The village we burned on the march. The officer called it a tactical necessity. I called it something else.", 95, -90),
            ("Mira hid me in the cellar the first night. She did not ask questions. That is the only kindness I remember.", 88, 70),
        ],
        "secret": ("He knows the Iron Legion's intended route through the city — information the guard captain would kill for.", 95),
    },
}

# ---------------------------------------------------------------------------
# H2.2 LOCATED_AT edges for new NPCs
# ---------------------------------------------------------------------------

H2_NPC_LOCATED_AT: list[tuple] = [
    (NPC_ID_BREN_SMITH, LOC_ID_FORGE),
    (NPC_ID_NESSA_PRIESTESS, LOC_ID_TEMPLE),
    (NPC_ID_DORN_DOCKMASTER, LOC_ID_DOCKS),
    (NPC_ID_VEX_SPYMASTER, "loc_guard_barracks"),
    (NPC_ID_TILDA_HERBALIST, "loc_market_square"),
    (NPC_ID_GARRICK_DESERTER, "loc_tavern"),
]

# ---------------------------------------------------------------------------
# H2.2 NPC Needs: (npc_id, kind, level 0-100, decay_rate per tick)
# ---------------------------------------------------------------------------

H2_NPC_NEEDS: list[tuple] = [
    (NPC_ID_BREN_SMITH, "hunger", 45, 3),
    (NPC_ID_BREN_SMITH, "recreation", 20, 2),
    (NPC_ID_NESSA_PRIESTESS, "social", 55, 1),
    (NPC_ID_NESSA_PRIESTESS, "rest", 60, 2),
    (NPC_ID_DORN_DOCKMASTER, "rest", 40, 3),
    (NPC_ID_DORN_DOCKMASTER, "social", 50, 2),
    (NPC_ID_VEX_SPYMASTER, "rest", 35, 3),
    (NPC_ID_VEX_SPYMASTER, "social", 30, 1),
    (NPC_ID_TILDA_HERBALIST, "hunger", 55, 3),
    (NPC_ID_TILDA_HERBALIST, "recreation", 40, 2),
    (NPC_ID_GARRICK_DESERTER, "rest", 20, 4),
    (NPC_ID_GARRICK_DESERTER, "social", 25, 2),
]

# ---------------------------------------------------------------------------
# H2.3 new locations:
# (id, name, location_tag, descriptor)
# ---------------------------------------------------------------------------

H2_LOCATIONS: list[tuple] = [
    (LOC_ID_FORGE, "The Forge", "forge",
     "A smoky workshop on Forge Row where iron is shaped into arms and tools."),
    (LOC_ID_TEMPLE, "Temple of the Unnamed", "temple",
     "A soot-stained stone temple; the one place all factions leave unwatched."),
    (LOC_ID_DOCKS, "The Docks", "docks",
     "A salt-worn harbour district where manifests lie and crates move at night."),
    (LOC_ID_NORTH_GATE, "North Gate", "gate",
     "The fortified northern entry to the city — a strategic chokepoint under guard scrutiny."),
]

# District-tier locations (hierarchy_level=1):
# (id, name, location_tag, descriptor)
H2_DISTRICTS: list[tuple] = [
    (LOC_ID_OLD_QUARTER, "Old Quarter", "district",
     "The ancient inner district containing the temple and the forge row."),
    (LOC_ID_HARBOR_DISTRICT, "Harbor District", "district",
     "The dockside district where maritime trade and smuggling share the same alley."),
]

# PART_OF hierarchy edges:
# (child_id, parent_id, hierarchy_level)
# hierarchy_level 0 = venue, 1 = district, 2 = city (per client.py:789)
H2_PART_OF_EDGES: list[tuple] = [
    # Venue → district
    (LOC_ID_FORGE, LOC_ID_OLD_QUARTER, 0),
    (LOC_ID_TEMPLE, LOC_ID_OLD_QUARTER, 0),
    (LOC_ID_DOCKS, LOC_ID_HARBOR_DISTRICT, 0),
    (LOC_ID_NORTH_GATE, LOC_ID_HARBOR_DISTRICT, 0),
    # District → city
    (LOC_ID_OLD_QUARTER, "loc_city", 1),
    (LOC_ID_HARBOR_DISTRICT, "loc_city", 1),
]

# ---------------------------------------------------------------------------
# H2.4 new factions:
# (id, name, archetype, description)
# ---------------------------------------------------------------------------

H2_FACTIONS: list[tuple] = [
    (
        FACTION_ID_CROWN_LOYALISTS,
        "Crown Loyalists",
        "political",
        "Agents of the distant crown, brokering treaties and tracking loyalties in the city.",
    ),
    (
        FACTION_ID_DOCKSIDE_SMUGGLERS,
        "Dockside Smugglers",
        "criminal",
        "A clandestine ring that profits from the war by moving contraband through the harbor.",
    ),
]

# H2.4 faction-faction STANDS_WITH edges:
# (src_faction_id, dst_faction_id, standing)
H2_FACTION_STANDS_WITH: list[tuple] = [
    (FACTION_ID_CROWN_LOYALISTS, "iron_legion", -90),
    (FACTION_ID_CROWN_LOYALISTS, "city_guard", 30),
    (FACTION_ID_DOCKSIDE_SMUGGLERS, "thieves_guild", 50),
    (FACTION_ID_DOCKSIDE_SMUGGLERS, "city_guard", -70),
]

# ---------------------------------------------------------------------------
# H2.5 new quest chains — 6 chains, 12 new quests + the Aldric quest = 18 total
#
# WIN_QUEST_CHAIN_IDS in constants.py already contains:
#   aldric_deliver_quest, demo_patrol_duty, demo_missing_goods,
#   demo_captain_report, demo_fence_confrontation
# New quests seeded here use ids consistent with the win path set to be
# extended in constants.py (see H2_WIN_QUEST_CHAIN_IDS below).
# ---------------------------------------------------------------------------

# Chain 1: Blacksmith Supply Run (bren_smith, city_guard-aligned)
# Source quest → chain quest (UNLOCKS on complete)
H2_SOURCE_CHAIN_QUESTS: list[dict] = [
    {
        "id": "bren_deliver_ore",
        "description": "Deliver iron ore to the forge so Bren can complete the guard's weapon order.",
        "quest_giver_id": NPC_ID_BREN_SMITH,
        "success_condition": "Bring iron ore to Bren at the forge.",
        "status": "offered",
        "severity": 35,
    },
    {
        "id": "tilda_gather_herbs",
        "description": "Gather northwood bark from the market stalls for Tilda's supply.",
        "quest_giver_id": NPC_ID_TILDA_HERBALIST,
        "success_condition": "Bring northwood bark to Tilda at the market.",
        "status": "offered",
        "severity": 30,
    },
    {
        "id": "dorn_inspect_manifests",
        "description": "Check three dock manifests for discrepancies and report to Dorn.",
        "quest_giver_id": NPC_ID_DORN_DOCKMASTER,
        "success_condition": "Investigate the dock manifests and return findings to Dorn.",
        "status": "offered",
        "severity": 40,
    },
    {
        "id": "nessa_deliver_medicine",
        "description": "Bring Nessa's medicine bundle to the sick family in the old quarter.",
        "quest_giver_id": NPC_ID_NESSA_PRIESTESS,
        "success_condition": "Deliver the medicine bundle to the sick family and return to Nessa.",
        "status": "offered",
        "severity": 30,
    },
    {
        "id": "vex_gather_leverage",
        "description": "Collect evidence of the smuggling ring's dockside operation for Vex.",
        "quest_giver_id": NPC_ID_VEX_SPYMASTER,
        "success_condition": "Gather dockside evidence and report to Vex at the barracks.",
        "status": "offered",
        "severity": 50,
    },
    {
        "id": "garrick_deliver_warning",
        "description": "Carry Garrick's sealed letter to the guard captain without revealing the sender.",
        "quest_giver_id": NPC_ID_GARRICK_DESERTER,
        "success_condition": "Deliver Garrick's warning letter to Captain Sorn.",
        "status": "offered",
        "severity": 60,
    },
]

# Chain (successor) quests unlocked on completion of the source quests above
H2_CHAIN_QUESTS: list[dict] = [
    {
        "id": "bren_guard_report",
        "description": "Report the completed weapon order to Captain Sorn on Bren's behalf.",
        "quest_giver_id": NPC_ID_BREN_SMITH,
        "success_condition": "Tell Captain Sorn the new weapons are ready at the forge.",
        "status": "offered",
        "severity": 40,
    },
    {
        "id": "tilda_compound_delivery",
        "description": "Bring Tilda's compounded remedy to Dorn at the docks — he owes her a favour.",
        "quest_giver_id": NPC_ID_TILDA_HERBALIST,
        "success_condition": "Deliver the remedy to Dorn and collect the promised ledger page.",
        "status": "offered",
        "severity": 40,
    },
    {
        "id": "dorn_confront_smuggler",
        "description": "Confront the dock worker Dorn suspects of skimming off shipments.",
        "quest_giver_id": NPC_ID_DORN_DOCKMASTER,
        "success_condition": "Speak with the dock worker and report the outcome to Dorn.",
        "status": "offered",
        "severity": 50,
    },
    {
        "id": "nessa_hear_confession",
        "description": "Escort the guild contact who wants to make a confession to the temple safely.",
        "quest_giver_id": NPC_ID_NESSA_PRIESTESS,
        "success_condition": "Bring the contact to the temple and wait outside for Nessa's signal.",
        "status": "offered",
        "severity": 40,
    },
    {
        "id": "vex_broker_accord",
        "description": "Use the collected evidence to pressure both factions into meeting Vex's terms.",
        "quest_giver_id": NPC_ID_VEX_SPYMASTER,
        "success_condition": "Report the outcome of the accord negotiation to Vex.",
        "status": "offered",
        "severity": 60,
    },
    {
        "id": "garrick_safe_passage",
        "description": "Arrange for Garrick to leave the city through the north gate before the guard realizes he is a deserter.",
        "quest_giver_id": NPC_ID_GARRICK_DESERTER,
        "success_condition": "Help Garrick reach the north gate undetected.",
        "status": "offered",
        "severity": 70,
    },
]

# UNLOCKS chain edges: (source_quest_id, chain_quest_id, on_outcome)
H2_QUEST_UNLOCKS_CHAINS: list[tuple] = [
    ("bren_deliver_ore", "bren_guard_report", "complete"),
    ("tilda_gather_herbs", "tilda_compound_delivery", "complete"),
    ("dorn_inspect_manifests", "dorn_confront_smuggler", "complete"),
    ("nessa_deliver_medicine", "nessa_hear_confession", "complete"),
    ("vex_gather_leverage", "vex_broker_accord", "complete"),
    ("garrick_deliver_warning", "garrick_safe_passage", "complete"),
]

# Quest IDs that count toward the quest-chain win (H1 economy extension).
# These augment WIN_QUEST_CHAIN_IDS in constants.py.
# We add the 6 successor (chain) quest IDs as win-eligible completions.
H2_WIN_QUEST_IDS: frozenset[str] = frozenset(
    {
        "bren_guard_report",
        "tilda_compound_delivery",
        "dorn_confront_smuggler",
        "nessa_hear_confession",
        "vex_broker_accord",
        "garrick_safe_passage",
    }
)
