"""
Module: constants
Layer: demo_game
Purpose: Fixed world-layout constants derived from the seeded demo world.
         NPC-to-location mapping, display names, faction assignments,
         ordered location list, and the centralised UI colour palette.
Dependencies: none
Used by: demo_game.ui.game_window, demo_game.ui.widgets, demo_game.ui.left_panel,
         demo_game.ui.quest_panel

FACTION_COLOURS and NPC_FACTIONS are hardcoded from the demo seed (DEC-028).
Faction membership is stable for the 5-NPC Munich demo world; no API call needed.
PALETTE is the single source of truth for all UI colours (DEC-035).
"""

from __future__ import annotations

# Mapping from location_id to the NPC IDs present there (seeded in P2.2).
LOCATION_NPC_MAP: dict[str, list[str]] = {
    "loc_tavern": ["mira_innkeeper", "lira_fence"],
    "loc_market_square": ["aldric_merchant", "old_henryk"],
    "loc_guard_barracks": ["captain_sorn"],
}

# Human-readable names for each location button.
LOCATION_DISPLAY_NAMES: dict[str, str] = {
    "loc_tavern": "The Tavern",
    "loc_market_square": "Market Square",
    "loc_guard_barracks": "Guard Barracks",
}

# Human-readable NPC display names shown in the NPC list and response log.
NPC_DISPLAY_NAMES: dict[str, str] = {
    "mira_innkeeper": "Mira (Innkeeper)",
    "aldric_merchant": "Aldric (Merchant)",
    "captain_sorn": "Captain Sorn",
    "lira_fence": "Lira (Fence)",
    "old_henryk": "Old Henryk",
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
    "loc_tavern": (60, 35, 20),          # warm brown
    "loc_market_square": (30, 55, 30),   # muted green
    "loc_guard_barracks": (30, 30, 60),  # dark blue
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
    "merchants_guild": (200, 160, 80),   # gold
    "city_guard":      (80, 120, 200),   # blue
    "thieves_guild":   (128, 80, 200),   # purple
    "neutral":         (96, 96, 96),     # grey
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
# If the server dies mid-stream, ws.recv() raises TimeoutError after this delay and
# the WS worker breaks out, allowing clear_waiting() in the finally block to unlock UI.
NPC_DIALOGUE_TIMEOUT_S: float = 30.0

# S10.1 Spread Rumor action: default planted text and severity for the demo button.
# The text is intentionally provocative so the gossip distortion is visible.
SPREAD_RUMOR_TEXT: str = "A hooded stranger was seen leaving the castle gates at midnight carrying stolen gold."
SPREAD_RUMOR_SEVERITY: int = 70

# Faction membership for each demo NPC — derived from seed, stable for Munich demo.
# See DEC-028 for why this is hardcoded rather than fetched from the graph.
NPC_FACTIONS: dict[str, str] = {
    "mira_innkeeper":  "neutral",
    "aldric_merchant": "merchants_guild",
    "captain_sorn":    "city_guard",
    "lira_fence":      "thieves_guild",
    "old_henryk":      "neutral",
}
