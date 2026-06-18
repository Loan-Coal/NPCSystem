"""
Module: arc_choice
Layer: demo_game
Purpose: Enum of available demo arcs selectable from the start menu.
Dependencies: enum
Used by: demo_game.ui.start_menu, demo_game.__main__
"""

from __future__ import annotations

import enum


class ArcChoice(enum.Enum):
    """The four selectable demo arcs shown in the start menu.

    Values map 1-to-1 with keyboard shortcuts (1=MUNICH, 2=VILLAGE,
    3=TAVERN, 4=FREE_PLAY) and with the subprocess targets in __main__.
    """

    MUNICH = "munich"
    VILLAGE = "village"
    TAVERN = "tavern"
    FREE_PLAY = "free_play"
