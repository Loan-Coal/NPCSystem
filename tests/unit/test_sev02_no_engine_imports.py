"""
Regression test for SEV-02: demo_game must not import from npc_engine.

Verifies the layer rule: demo_game is a pure REST/WS client and must have
zero imports from src/npc_engine.
"""

from __future__ import annotations

import re
from pathlib import Path

_DEMO_GAME_DIR = Path(__file__).resolve().parent.parent.parent / "demo_game"
_FORBIDDEN = re.compile(r"^\s*(from npc_engine|import npc_engine)", re.MULTILINE)


def _violations() -> list[str]:
    found = []
    for py_file in sorted(_DEMO_GAME_DIR.rglob("*.py")):
        src = py_file.read_text(encoding="utf-8")
        if _FORBIDDEN.search(src):
            found.append(str(py_file.relative_to(_DEMO_GAME_DIR.parent)))
    return found


def test_no_npc_engine_imports_in_demo_game() -> None:
    """demo_game/ must contain zero `from npc_engine` or `import npc_engine` lines."""
    bad = _violations()
    assert not bad, (
        "demo_game files still import npc_engine (SEV-02):\n  " + "\n  ".join(bad)
    )
