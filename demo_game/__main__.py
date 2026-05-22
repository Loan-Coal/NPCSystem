"""
Module: __main__
Layer: demo_game
Purpose: Entry point for `python -m demo_game`. Delegates to game_window.run().
Dependencies: demo_game.ui.game_window
Used by: `make demo`
"""

from __future__ import annotations

from demo_game.ui.game_window import run

run()
