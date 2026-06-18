"""
Module: __main__
Layer: demo_game
Purpose: Entry point for `python -m demo_game`. Parses --size arg, shows the
         start-menu, then delegates to the chosen arc runner or game_window.
Dependencies: demo_game._dispatch
Used by: `make demo`
"""

from __future__ import annotations

import argparse

from demo_game import _dispatch


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the demo launcher.

    Returns:
        Namespace with a ``size`` attribute formatted as ``WxH``.
    """
    parser = argparse.ArgumentParser(description="NPC Engine demo launcher")
    parser.add_argument(
        "--size",
        default="1280x720",
        help="Window size as WxH, e.g. --size 1920x1080",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    w, h = (int(v) for v in args.size.split("x"))
    _dispatch(window_w=w, window_h=h)
