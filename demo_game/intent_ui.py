"""
Module: intent_ui
Layer: demo_game (external client — zero npc_engine imports)
Purpose: UI constants for the NPC-initiative intent bubble overlay (Phase 14).
         Maps trigger types to display phrases and defines timing constants.
Dependencies: none
Used by: demo_game.npc_initiative_poller, demo_game.ui.game_window
"""

from __future__ import annotations

TRIGGER_PHRASES: dict[str, str] = {
    "need": "I could use your help with...",
    "event": "Did you hear about...",
    "goal": "There's something I need to discuss...",
}

INTENT_POLL_INTERVAL_SECONDS: float = 5.0
INTENT_BUBBLE_DISPLAY_SECONDS: float = 4.0
