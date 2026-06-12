"""
Module: constants
Layer: demo_game
Purpose: Fixed world-layout constants derived from the seeded demo world.
         NPC-to-location mapping, display names, faction assignments,
         ordered location list, the centralised UI colour palette, and
         H1 economy win/lose thresholds.
Dependencies: none
Used by: demo_game.ui.game_window, demo_game.ui.widgets, demo_game.ui.left_panel,
         demo_game.ui.quest_panel, demo_game.game_end_checker,
         demo_game.game_end_poller

FACTION_COLOURS and NPC_FACTIONS are hardcoded from the demo seed (DEC-028).
Faction membership is stable for the Munich demo world; no API call needed.
PALETTE is the single source of truth for all UI colours (DEC-035).

EXP-223: added 3 new NPCs (sera_barmaid, harwick_guard, nel_pickpocket) and
         1 new location (loc_chapel) within existing factions.
H1: added economy win/lose threshold constants (DEMO-D3-01 through D3-06).
H2.2-H2.5: added 6 new NPCs, 4 new locations + 2 districts, 2 new factions,
            12 new quests across 6 chains; WIN_QUEST_CHAIN_IDS extended.
"""

from __future__ import annotations

from demo_game.seed_npc_data import (
    FACTION_ID_CROWN_LOYALISTS,
    FACTION_ID_DOCKSIDE_SMUGGLERS,
    LOC_ID_DOCKS,
    LOC_ID_FORGE,
    LOC_ID_HARBOR_DISTRICT,
    LOC_ID_NORTH_GATE,
    LOC_ID_OLD_QUARTER,
    LOC_ID_TEMPLE,
    NPC_ID_BREN_SMITH,
    NPC_ID_DORN_DOCKMASTER,
    NPC_ID_GARRICK_DESERTER,
    NPC_ID_NESSA_PRIESTESS,
    NPC_ID_TILDA_HERBALIST,
    NPC_ID_VEX_SPYMASTER,
    H2_WIN_QUEST_IDS,
)

# ---------------------------------------------------------------------------
# EXP-223: stable NPC and location ID constants for the expanded world
# ---------------------------------------------------------------------------

NPC_ID_SERA_BARMAID: str = "sera_barmaid"
NPC_ID_HARWICK_GUARD: str = "harwick_guard"
NPC_ID_NEL_PICKPOCKET: str = "nel_pickpocket"

LOC_ID_CHAPEL: str = "loc_chapel"

# Re-export H2 location IDs for consumers that import from constants
LOC_ID_FORGE = LOC_ID_FORGE
LOC_ID_TEMPLE = LOC_ID_TEMPLE
LOC_ID_DOCKS = LOC_ID_DOCKS
LOC_ID_NORTH_GATE = LOC_ID_NORTH_GATE
LOC_ID_OLD_QUARTER = LOC_ID_OLD_QUARTER
LOC_ID_HARBOR_DISTRICT = LOC_ID_HARBOR_DISTRICT

# Re-export H2 faction IDs for consumers that import from constants
FACTION_ID_CROWN_LOYALISTS = FACTION_ID_CROWN_LOYALISTS
FACTION_ID_DOCKSIDE_SMUGGLERS = FACTION_ID_DOCKSIDE_SMUGGLERS

# Mapping from location_id to the NPC IDs present there (seeded in P2.2).
# EXP-223: sera_barmaid and nel_pickpocket added to loc_tavern;
#          harwick_guard added to loc_guard_barracks;
#          loc_chapel added as a quiet neutral zone.
# H2.2: bren_smith at loc_forge; nessa_priestess at loc_temple;
#       dorn_dockmaster at loc_docks; vex_spymaster at loc_guard_barracks;
#       tilda_herbalist at loc_market_square; garrick_deserter at loc_tavern.
LOCATION_NPC_MAP: dict[str, list[str]] = {
    "loc_tavern": [
        "mira_innkeeper", "lira_fence",
        NPC_ID_SERA_BARMAID, NPC_ID_NEL_PICKPOCKET,
        NPC_ID_GARRICK_DESERTER,
    ],
    "loc_market_square": ["aldric_merchant", "old_henryk", NPC_ID_TILDA_HERBALIST],
    "loc_guard_barracks": ["captain_sorn", NPC_ID_HARWICK_GUARD, NPC_ID_VEX_SPYMASTER],
    LOC_ID_CHAPEL: [],
    LOC_ID_FORGE: [NPC_ID_BREN_SMITH],
    LOC_ID_TEMPLE: [NPC_ID_NESSA_PRIESTESS],
    LOC_ID_DOCKS: [NPC_ID_DORN_DOCKMASTER],
    LOC_ID_NORTH_GATE: [],
}

# Human-readable names for each location button.
LOCATION_DISPLAY_NAMES: dict[str, str] = {
    "loc_tavern": "The Tavern",
    "loc_market_square": "Market Square",
    "loc_guard_barracks": "Guard Barracks",
    LOC_ID_CHAPEL: "The Chapel",
    LOC_ID_FORGE: "The Forge",
    LOC_ID_TEMPLE: "Temple",
    LOC_ID_DOCKS: "The Docks",
    LOC_ID_NORTH_GATE: "North Gate",
    LOC_ID_OLD_QUARTER: "Old Quarter",
    LOC_ID_HARBOR_DISTRICT: "Harbor District",
}

# Human-readable NPC display names shown in the NPC list and response log.
NPC_DISPLAY_NAMES: dict[str, str] = {
    "mira_innkeeper": "Mira (Innkeeper)",
    "aldric_merchant": "Aldric (Merchant)",
    "captain_sorn": "Captain Sorn",
    "lira_fence": "Lira (Fence)",
    "old_henryk": "Old Henryk",
    NPC_ID_SERA_BARMAID: "Sera (Barmaid)",
    NPC_ID_HARWICK_GUARD: "Harwick (Guard)",
    NPC_ID_NEL_PICKPOCKET: "Nel (Pickpocket)",
    NPC_ID_BREN_SMITH: "Bren (Blacksmith)",
    NPC_ID_NESSA_PRIESTESS: "Nessa (Priestess)",
    NPC_ID_DORN_DOCKMASTER: "Dorn (Dockmaster)",
    NPC_ID_VEX_SPYMASTER: "Vex (Spymaster)",
    NPC_ID_TILDA_HERBALIST: "Tilda (Herbalist)",
    NPC_ID_GARRICK_DESERTER: "Garrick (Deserter)",
}

# Ordered list of location IDs; determines button order in the nav bar.
LOCATIONS: list[str] = list(LOCATION_NPC_MAP.keys())

# Inverse of LOCATION_NPC_MAP — maps each NPC to their home location.
NPC_LOCATION_MAP: dict[str, str] = {
    npc_id: loc_id
    for loc_id, npcs in LOCATION_NPC_MAP.items()
    for npc_id in npcs
}

# Background tint colours per location (RGB), used for the location bar.
LOCATION_TINTS: dict[str, tuple[int, int, int]] = {
    "loc_tavern":         (60, 35, 20),   # warm brown
    "loc_market_square":  (30, 55, 30),   # muted green
    "loc_guard_barracks": (30, 30, 60),   # dark blue
    LOC_ID_CHAPEL:        (50, 45, 30),   # muted gold — quiet stone
    LOC_ID_FORGE:         (55, 30, 20),   # dark orange — fire and iron
    LOC_ID_TEMPLE:        (45, 40, 55),   # muted violet — sacred stone
    LOC_ID_DOCKS:         (20, 40, 55),   # steel blue — harbour water
    LOC_ID_NORTH_GATE:    (35, 35, 45),   # grey-blue — fortified stone
    LOC_ID_OLD_QUARTER:   (40, 35, 30),   # dusty amber — old stones
    LOC_ID_HARBOR_DISTRICT: (25, 40, 50), # deep teal — harbour fog
}

# Centralised UI colour palette — single source of truth for all demo_game UI colours.
# Module-level _CLR_* aliases in UI files are kept for minimal diff but reference this dict.
PALETTE: dict[str, tuple[int, int, int]] = {
    "bg":     (13,  27,  42),   # #0D1B2A — main background (dark navy)
    "amber":  (212, 160, 23),   # #D4A017 — primary text / headings
    "white":  (232, 232, 232),  # #E8E8E8 — secondary body text
    "grey":   (107, 114, 128),  # #6B7280 — inactive / dim labels
    "red":    (192, 57,  43),   # #C0392B — alerts / errors
    "green":  (39,  174, 96),   # #27AE60 — positive / safe
    "panel":  (18,  36,  54),   # panel background (slightly lighter than bg)
    "border": (40,  60,  80),   # subtle panel border
}

# Faction dot colours (RGB) used in NpcListWidget rows.
FACTION_COLOURS: dict[str, tuple[int, int, int]] = {
    "merchants_guild":           (200, 160, 80),   # gold
    "city_guard":                (80, 120, 200),   # blue
    "thieves_guild":             (128, 80, 200),   # purple
    "neutral":                   (96, 96, 96),     # grey
    FACTION_ID_CROWN_LOYALISTS:  (220, 200, 100),  # bright gold — crown heraldry
    FACTION_ID_DOCKSIDE_SMUGGLERS: (60, 140, 140), # teal — harbour water
}

# Gold cost per bribe and standing gain applied to player's STANDS_WITH edge.
BRIBE_GOLD_COST: int = 20
BRIBE_STANDING_GAIN: int = 15

# S8.3 propagated-reputation act: player commits a notable act at market_square.
# Seeds a reputation_change Event that gossip-propagates to the tavern.
PROPAGATED_REP_FACTION: str = "merchants_guild"
PROPAGATED_REP_LOCATION: str = "loc_market_square"
PROPAGATED_REP_DELTA: int = 40

# Cache-key version for the demo LLM response cache.
# Bump this constant (not npc_engine's PROMPT_VERSION) when demo behaviour changes.
DEMO_CACHE_VERSION: str = "demo_v1"

# Preset dialogue message for the Trade action button.
# Used in action_bar.py, game_controller.py, and quest_trade_controller.py.
TRADE_INTENT_MESSAGE: str = "I'd like to trade."

# Client-side cap on player_message length before sending to the NPC Engine.
# Mirrors src/npc_engine/config.py MAX_PLAYER_MESSAGE_CHARS (default 1000).
DEMO_MAX_MESSAGE_CHARS: int = 1000

# Maximum seconds to wait for a single WebSocket frame from the dialogue endpoint.
# The server fully generates the dialogue before streaming (dialogue_ws.py), so the
# first frame waits the full LLM generation (~38s cold qwen2.5:14b). Must be >= the
# HTTP dialogue timeout (config.DemoConfig.NPC_DIALOGUE_TIMEOUT_S) or the WS recv
# trips before the first token (ISSUE-065). If the server dies mid-stream, ws.recv()
# raises TimeoutError after this delay and the worker unlocks the UI via clear_waiting().
NPC_DIALOGUE_TIMEOUT_S: float = 120.0

# S10.1 Spread Rumor action: default planted text and severity for the demo button.
# The text is intentionally provocative so the gossip distortion is visible.
SPREAD_RUMOR_TEXT: str = "A hooded stranger was seen leaving the castle gates at midnight carrying stolen gold."
SPREAD_RUMOR_SEVERITY: int = 70

# ---------------------------------------------------------------------------
# Faction win condition constants (originally in game_end_checker.py; moved
# here so all threshold constants live in one place per H1 design).
# ---------------------------------------------------------------------------

# Minimum standing to count a faction as "allied" for win/arc tracking.
WIN_STANDING_THRESHOLD: int = 50
# Number of demo factions that must reach WIN_STANDING_THRESHOLD to win via faction path.
WIN_MIN_FACTIONS: int = 2
# The five factions the player can ally with (win-eligible via faction standing path).
# crown_loyalists and dockside_smugglers are alliable but NOT win-eligible in H1's
# multi-faction win — DEMO_FACTIONS remains the three original factions so existing
# game_end_checker.py logic is unchanged (D3/H2.7 will parameterize per-world).
DEMO_FACTIONS: tuple[str, ...] = ("merchants_guild", "city_guard", "thieves_guild")

# ---------------------------------------------------------------------------
# H1 economy win/lose thresholds (DEMO-D3-01 through D3-06)
# ---------------------------------------------------------------------------

# --- Wealth axis (DEMO-D3-01 / DEMO-D3-02) ---
# Gold needed to trigger the wealth win path.  Must be reachable by trade/bribe
# surplus but not trivially so vs _PLAYER_STARTING_GOLD (seed.py:778 = 100).
WEALTH_WIN_THRESHOLD: int = 500
# Gold at or below this value triggers bankruptcy lose (armed only after gold > 0).
BANKRUPTCY_LOSE_THRESHOLD: int = 0

# --- Quest-chain axis (DEMO-D3-01) ---
# Minimum number of quest IDs from WIN_QUEST_CHAIN_IDS that must be "completed"
# to satisfy the quest-chain win path.
QUEST_CHAIN_WIN_COUNT: int = 3
# Quest IDs that count toward the quest-chain win.  Sourced from demo seed.
# H2.5: extended with the 6 new chain-successor quests from seed_npc_data.py.
# QUEST_CHAIN_WIN_COUNT (=3) means the player needs 3 of these 11 to win the chain path.
WIN_QUEST_CHAIN_IDS: frozenset[str] = frozenset(
    {
        "aldric_deliver_quest",
        "demo_patrol_duty",
        "demo_missing_goods",
        "demo_captain_report",
        "demo_fence_confrontation",
    }
    | H2_WIN_QUEST_IDS
)

# --- Tick-deadline axis (DEMO-D3-04) ---
# Number of ticks from the *start tick* (latched on first poll) before deadline.
# At 1 auto-tick per real-world second this gives ~40 s; adjust for balance.
DEADLINE_TICKS: int = 40

# --- Faction-tension axis (DEMO-D3-03) ---
# Standing floor below which a rival faction is considered "floored" (overreach).
RIVAL_FLOOR: int = -25
# Rival pairs: winning with the key faction at the expense of the value faction.
# Symmetric in spirit but stored directionally for the check_overreach predicate.
FACTION_RIVALS: dict[str, str] = {
    "merchants_guild": "thieves_guild",
    "city_guard": "thieves_guild",
}

# --- Grade thresholds (DEMO-D3-06) ---
# Scores are computed in compute_grade() from faction standings + gold + ticks.
GRADE_S_MIN_SCORE: int = 90
GRADE_A_MIN_SCORE: int = 70
GRADE_B_MIN_SCORE: int = 50
# Anything below GRADE_B_MIN_SCORE → "C".

# ---------------------------------------------------------------------------
# Faction membership for each demo NPC — derived from seed, stable for Munich demo.
# See DEC-028 for why this is hardcoded rather than fetched from the graph.
# EXP-223: three new NPCs added; all use existing factions (no new faction added).
# H2.2: six new NPCs added with new and existing faction assignments.
NPC_FACTIONS: dict[str, str] = {
    "mira_innkeeper":        "neutral",
    "aldric_merchant":       "merchants_guild",
    "captain_sorn":          "city_guard",
    "lira_fence":            "thieves_guild",
    "old_henryk":            "neutral",
    NPC_ID_SERA_BARMAID:     "neutral",
    NPC_ID_HARWICK_GUARD:    "city_guard",
    NPC_ID_NEL_PICKPOCKET:   "thieves_guild",
    NPC_ID_BREN_SMITH:       "city_guard",
    NPC_ID_NESSA_PRIESTESS:  "neutral",
    NPC_ID_DORN_DOCKMASTER:  "merchants_guild",
    NPC_ID_VEX_SPYMASTER:    FACTION_ID_CROWN_LOYALISTS,
    NPC_ID_TILDA_HERBALIST:  "thieves_guild",
    NPC_ID_GARRICK_DESERTER: "neutral",
}
