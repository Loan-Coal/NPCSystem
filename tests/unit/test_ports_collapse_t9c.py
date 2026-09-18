"""
Module: test_ports_collapse_t9c
Layer: tests
Purpose: Structural guard for T9.1c — verifies all 8 port files from census rows 9–16
         have been deleted after the collapse.
RED anchor: files still exist before the collapse; test fails.
GREEN: all 8 files absent after T9.1c is complete.
"""

from __future__ import annotations

from pathlib import Path

_PORTS_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "src" / "npc_engine" / "engines" / "ports"
)

_COLLAPSED_ROW_9_16 = [
    "player_model_port.py",
    "chapter_port.py",
    "emotion_bootstrap_port.py",
    "event_port.py",
    "proactive_memory_read_port.py",
    "knowledge_port.py",
    "memory_consolidation_port.py",
    "reputation_port.py",
]


def test_rows_9_16_port_files_deleted() -> None:
    """All 8 port files from census rows 9-16 must be absent after T9.1c collapse."""
    remaining = [f for f in _COLLAPSED_ROW_9_16 if (_PORTS_DIR / f).exists()]
    assert not remaining, (
        f"Port files that should have been collapsed still exist: {remaining}. "
        "Run T9.1c to delete them and update consuming engines."
    )
