"""
Module: seed_world_data
Layer: demo_game (external client)
Purpose: Data-only module containing all demo-world constants and seed data tables.
         No logic, no I/O — pure static data for the demo seeder.
Dependencies: demo_game.constants (stable NPC/location ID constants)
Used by: demo_game.seeds.seed_domain, demo_game.seeds.seed

300-LINE WAIVER (DEC-109 extended): this is a DATA-ONLY module. The world data
is inherently large; splitting one cohesive content set across more files would
be artificial. See DECISIONS.md DEC-109.
"""

from __future__ import annotations

from demo_game.constants import (
    LOC_ID_CHAPEL,
    NPC_ID_HARWICK_GUARD,
    NPC_ID_NEL_PICKPOCKET,
    NPC_ID_SERA_BARMAID,
)

# ---------------------------------------------------------------------------
# Location data
# ---------------------------------------------------------------------------

_LOCATIONS = [
    ("loc_tavern", "The Rusty Flagon", "tavern", "A well-worn tavern where travelers and locals share ale and secrets."),
    ("loc_market_square", "Market Square", "market", "The beating heart of commerce, loud with haggling and rumor."),
    ("loc_guard_barracks", "Guard Barracks", "barracks", "The disciplined quarters of the city guard, smelling of iron and duty."),
    # EXP-223: new chapel location — quiet neutral ground between factions.
    (LOC_ID_CHAPEL, "The Chapel", "chapel", "A soot-stained stone chapel; the one place all factions leave alone."),
    # H2.3: four new venue locations (data from seed_npc_data.H2_LOCATIONS)
]

# ---------------------------------------------------------------------------
# Faction data
# ---------------------------------------------------------------------------

_FACTIONS = [
    ("merchants_guild", "Merchants Guild", "mercantile", "Controls the flow of trade through the city."),
    ("city_guard", "City Guard", "military", "Enforces the law and defends the city walls."),
    ("thieves_guild", "Thieves Guild", "criminal", "A shadow organization that lives in the cracks of the city."),
]

# Faction-faction relations via STANDS_WITH (negative standing = antagonism)
_FACTION_STANDS_WITH = [
    ("merchants_guild", "thieves_guild", -60),
    ("city_guard", "thieves_guild", -80),
]

# Extra faction for the Iron Legion (northern invaders from northern_war_begins event)
_MILITARY_FACTIONS: list[tuple[str, str, str, str]] = [
    ("iron_legion", "Iron Legion", "military", "The northern army that crossed the border at the start of the war."),
]

# ---------------------------------------------------------------------------
# Character data
# ---------------------------------------------------------------------------

_NPCS = [
    # (id, name, archetype, faction_id, location_id, biography, gossipy, credulity, honesty, voice_descriptor)
    ("mira_innkeeper", "Mira", "innkeeper", "neutral", "loc_tavern",
     "Runs the Rusty Flagon with an even hand and a sharp ear.", 60, 55, 70,
     "Warm, observant. Cautious about politics — never says more than she needs to."
     " Frames hard news as rumour or second-hand. Invites the listener to share what they know in return."),
    ("aldric_merchant", "Aldric", "merchant", "merchants_guild", "loc_market_square",
     "A veteran spice trader who knows every coin's worth and every man's price.", 50, 40, 65,
     "Measured and precise. Every statement is a negotiation — he gives only what serves him."
     " Refers to value, leverage, and risk. Distrusts sentiment."),
    ("captain_sorn", "Captain Sorn", "guard_captain", "city_guard", "loc_guard_barracks",
     "Commands the city watch with iron discipline and growing dread.", 25, 35, 85,
     "Clipped military diction. Direct. Names the enemy without emotion or hesitation."
     " No hedging, no qualifiers. Every sentence lands like a report to a superior officer."),
    ("lira_fence", "Lira", "fence", "thieves_guild", "loc_tavern",
     "Moves stolen goods with a smile and a story, always one step ahead.", 75, 45, 30,
     "Light, deflective. Turns every question into a joke or a counter-question."
     " Never volunteers information — makes you earn it. Laughs easily; means very little of it."),
    ("old_henryk", "Old Henryk", "elder", "neutral", "loc_market_square",
     "A retired courier who has seen three wars and remembers every one.", 80, 70, 80,
     "Rambling. Mixes current rumour with personal memories from decades ago."
     " Speaks with complete confidence even about details he has wrong. Never hedges."),
    # EXP-223: three new NPCs within existing factions
    (NPC_ID_SERA_BARMAID, "Sera", "barmaid", "neutral", "loc_tavern",
     "Mira's assistant, quick with a cloth and quicker with her ears.", 70, 65, 60,
     "Friendly and light, but vague when asked directly. Deflects with chores and small talk."),
    (NPC_ID_HARWICK_GUARD, "Harwick", "guard", "city_guard", "loc_guard_barracks",
     "A rank-and-file soldier who follows orders and tries not to think too hard.", 30, 60, 75,
     "Blunt and literal. Trusts his officers. Uncomfortable with ambiguity."),
    (NPC_ID_NEL_PICKPOCKET, "Nel", "pickpocket", "thieves_guild", "loc_tavern",
     "A young guild runner who moves between tables and pockets without anyone noticing.", 65, 55, 25,
     "Evasive, fast-talking. Denies everything. Pretends to be younger and more innocent than she is."),
]

# NPC faction membership: (npc_id, faction_id, role)
# EXP-223: harwick_guard and nel_pickpocket added to existing factions.
_NPC_MEMBER_OF = [
    ("aldric_merchant", "merchants_guild", "officer"),
    ("captain_sorn", "city_guard", "officer"),
    ("lira_fence", "thieves_guild", "member"),
    (NPC_ID_HARWICK_GUARD, "city_guard", "soldier"),
    (NPC_ID_NEL_PICKPOCKET, "thieves_guild", "runner"),
]

# Inner life: keyed by npc_id
_NPC_INNER_LIFE: dict[str, dict] = {
    "mira_innkeeper": {
        "beliefs": [
            ("The war will come here eventually — I have seen it before.", 70),
            ("People reveal their true nature after the second drink.", 80),
        ],
        "goals": [
            ("Keep the Rusty Flagon a neutral ground where all factions are welcome.", 60),
        ],
        "memories": [
            ("The night a deserter begged at my door in the rain. I hid him in the cellar for a week.", 85, 65),
            ("The last time the city went to war — half my regulars never came back.", 90, -75),
            ("A stranger came in asking about the northern war. Nervous eyes, too many questions. I told them what little I knew.", 80, 30),
        ],
        "secret": ("She hid a deserter from the city guard last winter.", 75),
    },
    "aldric_merchant": {
        "beliefs": [
            ("The guild protects those who pay their dues — and devours those who don't.", 65),
            ("Thieves are a plague on honest commerce and should be hanged.", 85),
        ],
        "goals": [
            ("Corner the northern spice trade before the war closes the roads.", 70),
            ("Expose the guild spy who has been skimming from the market accounts.", 55),
        ],
        "memories": [
            ("The night the south warehouse burned. I saw the guild master watching from across the street.", 88, 80),
            ("The day I signed my first guild contract — I did not read it carefully enough.", 70, -50),
        ],
        "secret": ("He has been skimming a tenth from his own guild tithe for two years.", 80),
    },
    "captain_sorn": {
        "beliefs": [
            ("The thieves guild is planning something large — the signs are all there.", 90),
            ("The city walls have never been in worse repair. One hard winter could break us.", 75),
        ],
        "goals": [
            ("Catch Lira in a crime significant enough to break the guild's protection racket.", 80),
        ],
        "memories": [
            ("The morning I found the gate sergeant's bribe money hidden in his boot. I said nothing.", 82, -60),
            ("The day I was promoted to captain — my predecessor disappeared the same week.", 78, 40),
        ],
        "secret": ("He knows the name of the merchant who bribed the gate sergeant and has done nothing.", 70),
    },
    "lira_fence": {
        "beliefs": [
            ("Every guard has a price — you just have to find the right currency.", 80),
            ("Aldric's ledger holds enough guild secrets to bury half the market.", 70),
        ],
        "goals": [
            ("Get that ledger from Aldric before he realizes what it proves.", 85),
        ],
        "memories": [
            ("The night I moved a crate of stolen army supplies through the market. No one asked questions.", 75, 55),
            ("The first time I was caught — I was twelve, and the merchant let me go. I never forgot.", 90, 70),
        ],
        "secret": ("She is currently fencing a shipment of stolen city guard armor.", 90),
    },
    "old_henryk": {
        "beliefs": [
            ("War changes everything about a place — the smell of fear never leaves.", 85),
            ("Young captains always underestimate the thieves until it is too late.", 65),
        ],
        "goals": [
            ("Warn the right people before it is too late — but find out who the right people are first.", 50),
        ],
        "memories": [
            ("Running dispatches through the north pass during the last war. Half my route was behind enemy lines.", 92, -80, True),
            ("The evening I found the smuggler's cache in the old mill — I marked it and walked away.", 80, 45),
        ],
        "secret": ("He knows the location of an old smuggler's cache beneath the north mill.", 60),
    },
    # EXP-223: inner life for the three new NPCs
    NPC_ID_SERA_BARMAID: {
        "beliefs": [
            ("The Rusty Flagon is the safest place in the city — as long as Mira keeps it neutral.", 70),
            ("People talk too freely after the second round. I make sure to remember.", 75),
        ],
        "goals": [
            ("Save enough to leave the city before the war reaches the gates.", 55),
        ],
        "memories": [
            ("A hooded man slipped Lira a folded note last Tenday. Neither noticed me refilling their cups.", 78, 40),
            ("The night a drunk guard let slip where the captain hides his private ledger.", 82, 50),
        ],
        "secret": ("She has been passing small items to a guild contact — unaware she is being used as a dead drop.", 65),
    },
    NPC_ID_HARWICK_GUARD: {
        "beliefs": [
            ("The captain's orders come down clean and you follow them. That is the whole job.", 80),
            ("Something is off at the south gate — the sergeant is too relaxed for a wartime posting.", 55),
        ],
        "goals": [
            ("Get through this posting without ending up on the wrong side of the captain's temper.", 60),
        ],
        "memories": [
            ("The morning a merchant bribed the gate sergeant and I pretended not to see.", 70, -45),
            ("Drill practice the week before the war declaration — nobody believed the orders were real.", 65, 30),
        ],
        "secret": ("He reported the bribe anonymously to the watch but the note was never acknowledged.", 50),
    },
    NPC_ID_NEL_PICKPOCKET: {
        "beliefs": [
            ("Everyone in this city is running a con. The only difference is how big.", 80),
            ("Lira is testing me. Every job she gives me is a test.", 70),
        ],
        "goals": [
            ("Prove herself to Lira by lifting something from the merchant quarter without getting caught.", 75),
        ],
        "memories": [
            ("The first purse I ever cut — a guild veteran's, as a test. He let me keep three coins.", 85, 60),
            ("Hiding under a market stall when the guard swept the square looking for a thief. Not me, that time.", 75, 35),
        ],
        "secret": ("She took a personal ring from the last job and hid it — Lira does not know yet.", 70),
    },
}

# LOCATED_AT edges: (npc_id, location_id)
# EXP-223: three new NPCs added at their home locations.
_NPC_LOCATED_AT: list[tuple[str, str]] = [
    ("mira_innkeeper", "loc_tavern"),
    ("lira_fence", "loc_tavern"),
    ("aldric_merchant", "loc_market_square"),
    ("old_henryk", "loc_market_square"),
    ("captain_sorn", "loc_guard_barracks"),
    (NPC_ID_SERA_BARMAID, "loc_tavern"),
    (NPC_ID_HARWICK_GUARD, "loc_guard_barracks"),
    (NPC_ID_NEL_PICKPOCKET, "loc_tavern"),
]

# ---------------------------------------------------------------------------
# NPC Needs
# ---------------------------------------------------------------------------

# NPC Needs: (npc_id, kind, level 0-100 where 0=critical, decay_rate per tick)
_NPC_NEEDS: list[tuple[str, str, int, int]] = [
    # mira_innkeeper — busy social hub, rests poorly
    ("mira_innkeeper", "social",     85, 2),
    ("mira_innkeeper", "rest",       35, 4),
    # aldric_merchant — driven, skips meals
    ("aldric_merchant", "hunger",    28, 3),
    ("aldric_merchant", "social",    60, 2),
    # captain_sorn — disciplined but exhausted
    ("captain_sorn", "rest",         20, 5),
    ("captain_sorn", "recreation",   45, 2),
    # lira_fence — cautious, keeps to herself
    ("lira_fence", "social",         70, 2),
    ("lira_fence", "rest",           55, 3),
    # old_henryk — worn down, needs rest most
    ("old_henryk", "rest",           15, 4),
    ("old_henryk", "hunger",         50, 3),
    # EXP-223 new NPCs
    # sera_barmaid — always on her feet, socially fulfilled but physically exhausted
    (NPC_ID_SERA_BARMAID, "rest",    25, 5),
    (NPC_ID_SERA_BARMAID, "social",  75, 1),
    # harwick_guard — disciplined routine, bored from repetitive duty
    (NPC_ID_HARWICK_GUARD, "recreation", 30, 2),
    (NPC_ID_HARWICK_GUARD, "rest",       55, 3),
    # nel_pickpocket — anxious, high social need (information gathering)
    (NPC_ID_NEL_PICKPOCKET, "social",    80, 3),
    (NPC_ID_NEL_PICKPOCKET, "hunger",    40, 4),
]

# ---------------------------------------------------------------------------
# Military layer — armies for S6.6 battle demo
# ---------------------------------------------------------------------------

# Army nodes: (id, faction_id, strength, current_location_id, composition)
_ARMIES: list[tuple[str, str, int, str, str]] = [
    (
        "army_iron_legion",
        "iron_legion",
        100,
        "loc_north_gate",
        '{"infantry": 80, "cavalry": 15, "siege": 5}',
    ),
    (
        "army_city_guard_main",
        "city_guard",
        60,
        "loc_guard_barracks",
        '{"infantry": 55, "cavalry": 5, "siege": 0}',
    ),
]

# OCCUPIES edges: (army_id, location_id, since_tick)
_ARMY_OCCUPIES: list[tuple[str, str, int]] = [
    ("army_iron_legion", "loc_north_gate", 0),
    ("army_city_guard_main", "loc_guard_barracks", 0),
]

# ---------------------------------------------------------------------------
# Political layer — leverage and pledges
# ---------------------------------------------------------------------------

# Leverage nodes: (id, demand, status, created_at_tick)
_LEVERAGE_NODES: list[tuple[str, str, str, int]] = [
    (
        "lv_lira_over_aldric",
        "Reveal that Aldric has been skimming guild tithes unless he lets a shipment through",
        "held",
        0,
    ),
    (
        "lv_sorn_over_gate_sgt",
        "Demand the gate sergeant's loyalty in exchange for silence about the bribe",
        "held",
        0,
    ),
]

# HAS_LEVERAGE edges: (holder_npc_id, leverage_node_id)
_HAS_LEVERAGE_EDGES: list[tuple[str, str]] = [
    ("lira_fence", "lv_lira_over_aldric"),
    ("captain_sorn", "lv_sorn_over_gate_sgt"),
]

# Pledge seed data: (pledger_id, pledgee_id, pledge_type, tick)
# Using create_pledge via the typed pledges route (POST /v1/pledges/characters/{pledger_id})
_PLEDGE_SEED: list[tuple[str, str, str, int]] = [
    ("lira_fence", "thieves_guild", "fealty", 0),
    ("aldric_merchant", "merchants_guild", "fealty", 0),
]

# ---------------------------------------------------------------------------
# NPC-NPC edges (gossip path + structural relations)
# ---------------------------------------------------------------------------

# NPC-NPC edges: (edge_type, src_id, dst_id, properties)
_NPC_NPC_EDGES: list[tuple[str, str, str, dict]] = [
    ("RELATES_TO", "mira_innkeeper", "old_henryk", {
        "trust": 70, "affection": 50, "fear": 0,
        "relevance_score": 60, "interaction_count": 10,
        "last_updated_at": "tick_0",
    }),
    ("RELATES_TO", "lira_fence", "aldric_merchant", {
        "trust": 10, "affection": 0, "fear": 30,
        "relevance_score": 80, "interaction_count": 3,
        "last_updated_at": "tick_0",
    }),
    ("OPPOSES", "captain_sorn", "lira_fence", {
        "intensity": 85,
        "reason": "lira runs a criminal operation in the city",
        "established_tick": 0,
    }),
    # captain_sorn has direct, undistorted knowledge of the war (tick 0 seed)
    ("KNOWS_ABOUT", "captain_sorn", "northern_war_begins", {
        "knowledge_state": "knows",
        "distortion_type": None,
        "distortion_level": 0,
        "distorted_summary": "The northern armies have crossed the border. We are at war.",
        "learned_at_tick": 0,
        "source_character_id": None,
    }),
    # Pre-seeded gossip chain for demo reliability (see DEC-006).
    ("KNOWS_ABOUT", "mira_innkeeper", "northern_war_begins", {
        "knowledge_state": "rumor",
        "distortion_type": "exaggeration",
        "distortion_level": 20,
        "distorted_summary": (
            "A soldier passing through told me the northern armies, the Iron Guard he called them,"
            " have moved on the border. Whether it is true I cannot say, but he seemed shaken."
        ),
        "learned_at_tick": 1,
        "source_character_id": "captain_sorn",
    }),
    ("KNOWS_ABOUT", "old_henryk", "northern_war_begins", {
        "knowledge_state": "rumor",
        "distortion_type": "exaggeration",
        "distortion_level": 70,
        # S26.3 (ISSUE-093): the firsthand past-war clause ("I ran dispatches through
        # king's pass in the last war") was split out into old_henryk's is_historical
        # memory. This rumour is current-war hearsay only — no firsthand framing.
        "distorted_summary": (
            "Word reached me the northmen have poured through king's pass, thousands dead."
            " Utterly catastrophic, they say — the northmen storming king's pass like that."
        ),
        "learned_at_tick": 2,
        "source_character_id": "mira_innkeeper",
    }),
    # Lira hears about the market fire through the tavern (fire is public; word spreads fast).
    ("KNOWS_ABOUT", "lira_fence", "market_fire", {
        "knowledge_state": "rumor",
        "distortion_type": None,
        "distortion_level": 10,
        "distorted_summary": (
            "Word spread through the tavern fast — fire in the square."
            " My kind of chaos, all those distracted guards."
        ),
        "learned_at_tick": 3,
        "source_character_id": None,
    }),
]

# ---------------------------------------------------------------------------
# Player, items, and deception constants
# ---------------------------------------------------------------------------

_PLAYER_ID = "player_demo"
_AMULET_ID = "ancient_amulet"
_ALDRIC_QUEST_ID = "aldric_deliver_quest"
_ALDRIC_REWARD_AMOUNT = 50
_SPICE_ID = "northern_spice_bundle"
_SPICE_VALUE = 120

# Player KNOWS_ABOUT edges (F3.6 / EXP-217) so GET /player/{id}/events returns data on
# a fresh seed. The player has firsthand, undistorted knowledge of two seeded public events.
# Applied AFTER the player Character is seeded (the edge source must exist first).
_PLAYER_KNOWS_ABOUT: list[tuple[str, dict]] = [
    ("northern_war_begins", {
        "knowledge_state": "knows",
        "distortion_type": None,
        "distortion_level": 0,
        "distorted_summary": "War has broken out in the north — the border has fallen.",
        "learned_at_tick": 0,
        "source_character_id": None,
    }),
    ("market_fire", {
        "knowledge_state": "knows",
        "distortion_type": None,
        "distortion_level": 0,
        "distorted_summary": "A fire tore through the market square.",
        "learned_at_tick": 0,
        "source_character_id": None,
    }),
]

# Planted deception belief (F2.5/G2.5/G3): lira_fence holds a deliberately-false belief she
# spreads to cover a heist. is_deception=true surfaces the buyer-facing "tell" (G2.5) and
# keeps the anti-hallucination eval from flagging the intended lie (F3.3) — content unchanged.
_DECEPTION_BELIEF_NPC = "lira_fence"
_DECEPTION_BELIEF_ID = "lira_planted_lie_mill"
_DECEPTION_BELIEF_CONTENT = "The city guard never patrols the old mill after dark."
_DECEPTION_GOAL_ID = "lira_heist_cover"

# ---------------------------------------------------------------------------
# Quest data
# ---------------------------------------------------------------------------

_QUEST_UNLOCKS_CHAINS: list[tuple[str, str, str]] = [
    ("demo_patrol_duty", "demo_captain_report", "complete"),
    ("demo_missing_goods", "demo_fence_confrontation", "complete"),
]

# Chain-target Quest nodes that must exist before UNLOCKS edges are wired (EXP-19 slice-3).
# These are the successor quests unlocked by _QUEST_UNLOCKS_CHAINS above.
_CHAIN_QUESTS: list[dict] = [
    {
        "id": "demo_captain_report",
        "description": "Report the patrol findings to the Captain.",
        "quest_giver_id": "captain_sorn",
        "success_condition": "Deliver the patrol report to Captain Sorn.",
        "status": "offered",
        "severity": 40,
    },
    {
        "id": "demo_fence_confrontation",
        "description": "Confront Lira about the missing goods.",
        "quest_giver_id": "lira_fence",
        "success_condition": "Speak with Lira at the tavern about the missing shipment.",
        "status": "offered",
        "severity": 50,
    },
]

# Source/trigger Quest nodes for the UNLOCKS chains (EXP-19 slice-4).
# These must exist so the chains can be fired by completing them.
_SOURCE_CHAIN_QUESTS: list[dict] = [
    {
        "id": "demo_patrol_duty",
        "description": "Patrol the northern road and report any suspicious activity.",
        "quest_giver_id": "captain_sorn",
        "success_condition": "Complete the patrol route and return to Captain Sorn.",
        "status": "offered",
        "severity": 35,
    },
    {
        "id": "demo_missing_goods",
        "description": "Investigate what happened to Aldric's missing shipment.",
        "quest_giver_id": "aldric_merchant",
        "success_condition": "Find out what happened to the missing goods.",
        "status": "offered",
        "severity": 45,
    },
]
