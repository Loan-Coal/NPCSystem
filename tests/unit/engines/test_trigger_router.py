"""Unit tests for engines.proactive_dialogue.trigger_router.

Tests cover:
  - select_trigger returns None for an empty candidate list.
  - select_trigger returns the single candidate when only one is provided.
  - select_trigger picks the highest-priority candidate.
  - Tie-breaking is deterministic (stable: lowest source alphabetically, then
    lowest payload string) so repeated calls return the same result.
"""

from __future__ import annotations

import pytest

from npc_engine.engines.proactive_dialogue.trigger_router import (
    TriggerCandidate,
    TriggerSource,
    select_trigger,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _candidate(
    source: str = "memory",
    priority: int = 50,
    payload: str = "p",
) -> TriggerCandidate:
    """Build a TriggerCandidate with minimal boilerplate."""
    return TriggerCandidate(source=source, priority=priority, payload=payload)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSelectTriggerNone:
    """select_trigger returns None when there are no candidates."""

    def test_select_trigger_none_when_empty(self) -> None:
        result = select_trigger([])
        assert result is None


class TestSelectTriggerSingle:
    """select_trigger returns the only candidate when the list has one entry."""

    def test_returns_single_candidate(self) -> None:
        c = _candidate(source="need", priority=30)
        result = select_trigger([c])
        assert result is c


class TestSelectTriggerHighestPriority:
    """select_trigger picks the highest-priority candidate."""

    def test_picks_highest_priority(self) -> None:
        low = _candidate(source="event", priority=10)
        high = _candidate(source="memory", priority=90)
        mid = _candidate(source="need", priority=50)
        result = select_trigger([low, high, mid])
        assert result is high

    def test_picks_highest_priority_regardless_of_order(self) -> None:
        high = _candidate(source="memory", priority=80)
        low1 = _candidate(source="event", priority=20)
        low2 = _candidate(source="need", priority=40)
        for candidates in [
            [high, low1, low2],
            [low1, high, low2],
            [low2, low1, high],
        ]:
            assert select_trigger(candidates) is high


class TestSelectTriggerTieBreak:
    """Tie-breaking is deterministic: alphabetically lowest source wins; on further
    tie, alphabetically lowest payload wins."""

    def test_tie_break_by_source_alphabetical(self) -> None:
        # "event" < "memory" < "need" alphabetically
        a = _candidate(source="need", priority=50, payload="x")
        b = _candidate(source="event", priority=50, payload="x")
        c = _candidate(source="memory", priority=50, payload="x")
        result = select_trigger([a, b, c])
        assert result is b  # "event" is lowest

    def test_tie_break_by_payload_when_source_equal(self) -> None:
        a = _candidate(source="memory", priority=50, payload="zebra")
        b = _candidate(source="memory", priority=50, payload="apple")
        result = select_trigger([a, b])
        assert result is b  # "apple" < "zebra"

    def test_tie_break_is_stable_across_repeated_calls(self) -> None:
        candidates = [
            _candidate(source="need", priority=70, payload="b"),
            _candidate(source="need", priority=70, payload="a"),
        ]
        first = select_trigger(candidates)
        second = select_trigger(candidates)
        assert first is second

    def test_all_literal_sources_accepted(self) -> None:
        """TriggerSource Literal covers memory, need, event — all accepted by Pydantic."""
        for src in ("memory", "need", "event"):
            c = _candidate(source=src, priority=1)
            assert c.source == src

    def test_invalid_source_rejected(self) -> None:
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            _candidate(source="unknown_source", priority=1)
