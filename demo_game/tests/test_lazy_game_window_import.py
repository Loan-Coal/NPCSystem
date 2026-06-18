"""
Module: test_lazy_game_window_import
Layer: demo_game (tests)
Purpose: Assert that `import demo_game` does NOT eagerly import the pygame-backed
         game_window module, so headless test collection never triggers SDL_Init
         at import time (ISSUE-091).
Dependencies: subprocess, sys
Used by: make test-demo
"""

from __future__ import annotations

import subprocess
import sys


def test_importing_demo_game_does_not_load_game_window() -> None:
    """A bare `import demo_game` must not pull in demo_game.ui.game_window."""
    code = (
        "import sys; import demo_game; "
        "print('demo_game.ui.game_window' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip().endswith("False"), result.stdout
