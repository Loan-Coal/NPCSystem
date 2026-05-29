"""
Module: __main__
Layer: demo_game
Purpose: Entry point for `python -m demo_game`. Parses --size arg and delegates to game_window.run().
Dependencies: demo_game.ui.game_window
Used by: `make demo`
"""

from __future__ import annotations

import argparse

from demo_game.ui.game_window import run


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NPC Engine demo window")
    parser.add_argument(
        "--size",
        default="1280x720",
        help="Window size as WxH, e.g. --size 1920x1080",
    )
    return parser.parse_args()


args = _parse_args()
w, h = (int(v) for v in args.size.split("x"))
run(window_w=w, window_h=h)
