"""
Package: demo_game
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Minimal playable demo game that calls the NPC Engine via HTTP.
Public surface: EngineClient, EngineClientError (from demo_game.client), _dispatch
"""

from __future__ import annotations

import subprocess
import sys

from demo_game.arc_choice import ArcChoice
from demo_game.ui.start_menu import StartMenu

# Subprocess module targets for scripted arcs.
_MODULE_MUNICH = "demo_game.run"
_MODULE_VILLAGE = "demo_game.scenarios.run_village_crisis"
_MODULE_TAVERN = "demo_game.scenarios.run_tavern_intrigue"

# Map from scripted arc → subprocess module string.
_ARC_MODULES: dict[ArcChoice, str] = {
    ArcChoice.MUNICH: _MODULE_MUNICH,
    ArcChoice.VILLAGE: _MODULE_VILLAGE,
    ArcChoice.TAVERN: _MODULE_TAVERN,
}


def _dispatch(window_w: int, window_h: int) -> None:
    """Show the start menu, then launch the chosen arc.

    FREE_PLAY opens game_window.run() in-process.
    All other arcs spawn a subprocess and return after it completes.

    Args:
        window_w: Width passed to the start menu and game window.
        window_h: Height passed to the start menu and game window.
    """
    choice = StartMenu().show(window_w=window_w, window_h=window_h)

    if choice == ArcChoice.FREE_PLAY:
        # Lazy import: keep the pygame-backed game_window off the `import demo_game`
        # path so headless test collection never triggers SDL_Init (ISSUE-091).
        import demo_game.ui.game_window as _game_window

        _game_window.run(window_w=window_w, window_h=window_h)
        return

    module = _ARC_MODULES[choice]
    subprocess.run([sys.executable, "-m", module], check=False)
