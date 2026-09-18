"""
Module: test_ports_collapse_t9b
Layer: tests
Purpose: Structural guard for T9.1b — verifies all 8 port files from census rows 1–8
         have been deleted after the collapse.
RED anchor: files still exist before the collapse; test fails.
GREEN: all 8 files absent after T9.1b is complete.
"""

from __future__ import annotations

from pathlib import Path

_PORTS_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "src" / "npc_engine" / "engines" / "ports"
)

_COLLAPSED_ROW_1_8 = [
    "emotion_port.py",
    "economy_port.py",
    "memory_port.py",
    "need_port.py",
    "routine_port.py",
    "story_pacing_port.py",
    "political_port.py",
    "investigation_port.py",
]


def test_rows_1_8_port_files_deleted() -> None:
    """All 8 port files from census rows 1-8 must be absent after T9.1b collapse."""
    remaining = [f for f in _COLLAPSED_ROW_1_8 if (_PORTS_DIR / f).exists()]
    assert not remaining, (
        f"Port files that should have been collapsed still exist: {remaining}. "
        "Run T9.1b to delete them and update consuming engines."
    )
