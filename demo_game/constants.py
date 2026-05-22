"""
Module: constants
Layer: demo_game
Purpose: Fixed world-layout constants derived from the seeded demo world.
         NPC-to-location mapping, display names, and ordered location list.
Dependencies: none
Used by: demo_game.ui.game_window, demo_game.ui.widgets
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

# Background tint colours per location (RGB), used for the location bar.
LOCATION_TINTS: dict[str, tuple[int, int, int]] = {
    "loc_tavern": (60, 35, 20),          # warm brown
    "loc_market_square": (30, 55, 30),   # muted green
    "loc_guard_barracks": (30, 30, 60),  # dark blue
}
