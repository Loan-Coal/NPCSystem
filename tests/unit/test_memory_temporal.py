"""
test_memory_temporal.py - Unit tests for memory age annotation (S26.2, ISSUE-093).

Memories must be framed as past recollections. annotate_memory_ages tags each memory
with a coarse 'age' (recent | long_past) from its event/record game-time vs the current
world time, so the dialogue prompt can stop NPCs presenting old experiences as current.
"""

from __future__ import annotations

import json

from npc_engine.retrieval.memory_temporal import (
    AGE_LONG_PAST,
    AGE_RECENT,
    annotate_memory_ages,
)
from npc_engine.world.time_utils import TimePoint


def _gt(year: int) -> str:
    return json.dumps({"year": year, "season": "spring", "day": 1, "time_of_day": "morning"})


_NOW = TimePoint(year=5, season="spring", day=1, time_of_day="morning")


def test_recent_memory_tagged_recent() -> None:
    """A memory recorded at the current year is recent."""
    out = annotate_memory_ages([{"content": "x", "created_at_game_time": _gt(5)}], _NOW)
    assert out[0]["age"] == AGE_RECENT


def test_old_memory_tagged_long_past() -> None:
    """A memory from year 1 (>= 365 game-days before year 5) is long_past."""
    out = annotate_memory_ages([{"content": "x", "created_at_game_time": _gt(1)}], _NOW)
    assert out[0]["age"] == AGE_LONG_PAST


def test_is_historical_flag_forces_long_past() -> None:
    """is_historical short-circuits to long_past regardless of timestamps (S26.3-ready)."""
    out = annotate_memory_ages([{"content": "x", "is_historical": True, "created_at_game_time": _gt(5)}], _NOW)
    assert out[0]["age"] == AGE_LONG_PAST


def test_occurred_at_preferred_over_created_at() -> None:
    """When occurred_at_game_time is present it drives age, not the record time."""
    mem = {"content": "x", "occurred_at_game_time": _gt(1), "created_at_game_time": _gt(5)}
    out = annotate_memory_ages([mem], _NOW)
    assert out[0]["age"] == AGE_LONG_PAST


def test_no_game_time_returns_unannotated_copy() -> None:
    """With no current game-time, memories pass through unchanged (no age key)."""
    out = annotate_memory_ages([{"content": "x"}], None)
    assert out == [{"content": "x"}]


def test_malformed_timestamp_defaults_recent() -> None:
    """A malformed game-time is treated as recent, never raises."""
    out = annotate_memory_ages([{"content": "x", "created_at_game_time": "not-json{{"}], _NOW)
    assert out[0]["age"] == AGE_RECENT


def test_annotation_does_not_mutate_input() -> None:
    """Input memory dicts are not mutated in place (immutability)."""
    mem = {"content": "x", "created_at_game_time": _gt(1)}
    annotate_memory_ages([mem], _NOW)
    assert "age" not in mem
