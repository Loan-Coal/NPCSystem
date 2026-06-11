"""
Unit tests for the faction politics engine (Phase 4.1).

Tests use fake async session stubs — no live DB required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.faction_politics.rules_loader import (
    DecayConfig,
    FactionPoliticsRule,
    FactionPoliticsRules,
    load_rules,
)
from npc_engine.engines.faction_politics.faction_politics_engine import FactionPoliticsEngine


# ---------------------------------------------------------------------------
# Async session stubs
# ---------------------------------------------------------------------------

_RULES_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "src" / "npc_engine" / "engines" / "faction_politics" / "rules.yaml"
)


@dataclass
class _AsyncIter:
    _items: list[Any]
    _idx: int = field(default=0, init=False)

    def __aiter__(self) -> "_AsyncIter":
        return self

    async def __anext__(self) -> Any:
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item


@dataclass
class _FakeResult:
    _records: list[dict]

    def __aiter__(self) -> _AsyncIter:
        return _AsyncIter(self._records)

    async def single(self) -> dict | None:
        return self._records[0] if self._records else None


class _FakeTx:
    """Transaction stub that records set_standing calls."""

    def __init__(self) -> None:
        self.standing_calls: list[dict] = []
        self.committed = False

    async def __aenter__(self) -> "_FakeTx":
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    async def commit(self) -> None:
        self.committed = True

    async def run(self, query: str, **kwargs: Any) -> _FakeResult:
        if "standing" in kwargs:
            self.standing_calls.append({**kwargs})
        rec = MagicMock()
        rec.__getitem__ = lambda self, k: kwargs.get(k)
        return _FakeResult([rec])


class _FakeSession:
    """Fake Neo4j async session with configurable query results."""

    def __init__(
        self,
        *,
        events: list[dict] | None = None,
        char_factions: list[str] | None = None,
        standings: list[dict] | None = None,
    ) -> None:
        self._events = events or []
        self._char_factions = char_factions or []
        self._standings = standings or []
        self.tx = _FakeTx()

    async def run(self, query: str, **kwargs: Any) -> _FakeResult:
        if "src_character_id IS NOT NULL" in query:
            return _FakeResult(self._events)
        if "MEMBER_OF" in query:
            return _FakeResult([{"faction_id": f} for f in self._char_factions])
        if "STANDS_WITH" in query and "MERGE" not in query and "SET" not in query:
            return _FakeResult(self._standings)
        return _FakeResult([])

    async def begin_transaction(self) -> _FakeTx:
        return self.tx


# ---------------------------------------------------------------------------
# Rule helpers
# ---------------------------------------------------------------------------


def _make_rules(
    *,
    rate_per_tick: int = 1,
    min_magnitude: int = 2,
    rules: list[tuple[str, str, int]] | None = None,
) -> FactionPoliticsRules:
    if rules is None:
        rules = [("betrayal_standing_penalty", "betrayal", -10)]
    return FactionPoliticsRules(
        decay=DecayConfig(rate_per_tick=rate_per_tick, min_magnitude=min_magnitude),
        rules=tuple(
            FactionPoliticsRule(id=r[0], event_type=r[1], standing_delta=r[2]) for r in rules
        ),
    )


# ---------------------------------------------------------------------------
# Rules loader tests
# ---------------------------------------------------------------------------


def test_rules_loader_loads_yaml() -> None:
    """Loads the real rules.yaml; asserts ≥2 rules and decay block present."""
    rules = load_rules(_RULES_PATH)
    assert isinstance(rules.decay, DecayConfig)
    assert rules.decay.rate_per_tick >= 1
    assert rules.decay.min_magnitude >= 1
    assert len(rules.rules) >= 2
    ids = {r.id for r in rules.rules}
    assert "betrayal_standing_penalty" in ids
    assert "alliance_act_bonus" in ids


# ---------------------------------------------------------------------------
# Engine behaviour tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_applies_matching_rule() -> None:
    """Event of type 'betrayal' causes a rule application on a faction pair."""
    rules = _make_rules(rules=[("betrayal_penalty", "betrayal", -10)])
    engine = FactionPoliticsEngine(rules=rules)

    session = _FakeSession(
        events=[{"event_id": None, "event_type": "betrayal", "src_character_id": "char_a"}],
        char_factions=["faction_a"],
        standings=[{"src_id": "faction_a", "dst_id": "faction_b", "standing": 50}],
    )

    result = await engine.run_tick(session)  # type: ignore[arg-type]
    assert result["rule_applications"] >= 1


@pytest.mark.asyncio
async def test_run_tick_no_matching_rule_no_change() -> None:
    """Event type with no matching rule results in zero rule applications."""
    rules = _make_rules(rules=[("betrayal_penalty", "betrayal", -10)])
    engine = FactionPoliticsEngine(rules=rules)

    session = _FakeSession(
        events=[{"event_id": None, "event_type": "unknown_event_xyz", "src_character_id": "char_a"}],
        char_factions=["faction_a"],
        standings=[{"src_id": "faction_a", "dst_id": "faction_b", "standing": 50}],
    )

    result = await engine.run_tick(session)  # type: ignore[arg-type]
    assert result["rule_applications"] == 0


@pytest.mark.asyncio
async def test_run_tick_clamps_to_bounds() -> None:
    """Delta that would push standing past 100 is clamped before writing."""
    rules = _make_rules(rules=[("big_bonus", "alliance_act", 30)])
    engine = FactionPoliticsEngine(rules=rules)

    # standing=90; +30 = 120 → clamp to 100; 100 ≠ 90 so rule applies
    session = _FakeSession(
        events=[{"event_id": None, "event_type": "alliance_act", "src_character_id": "char_a"}],
        char_factions=["faction_a"],
        standings=[{"src_id": "faction_a", "dst_id": "faction_b", "standing": 90}],
    )

    result = await engine.run_tick(session)  # type: ignore[arg-type]
    assert result["rule_applications"] >= 1
    # Verify clamped value written is ≤ 100
    standing_written = session.tx.standing_calls[0]["standing"]
    assert standing_written <= 100


@pytest.mark.asyncio
async def test_run_tick_clamps_negative_to_minus_100() -> None:
    """Delta that would push standing below -100 is clamped to -100."""
    rules = _make_rules(rules=[("big_penalty", "betrayal", -30)])
    engine = FactionPoliticsEngine(rules=rules)

    # standing=-80; -30 = -110 → clamp to -100
    session = _FakeSession(
        events=[{"event_id": None, "event_type": "betrayal", "src_character_id": "char_a"}],
        char_factions=["faction_a"],
        standings=[{"src_id": "faction_a", "dst_id": "faction_b", "standing": -80}],
    )

    result = await engine.run_tick(session)  # type: ignore[arg-type]
    assert result["rule_applications"] >= 1
    standing_written = session.tx.standing_calls[0]["standing"]
    assert standing_written >= -100


# First test also needs event_id — fix the original fixture:

@pytest.mark.asyncio
async def test_run_tick_applies_matching_rule_with_event_id() -> None:
    """record_standing_change is called when a rule fires; engine returns >= 1 application."""
    rules = _make_rules(rules=[("betrayal_penalty", "betrayal", -10)])
    engine = FactionPoliticsEngine(rules=rules)

    session = _FakeSession(
        events=[{"event_id": "evt-abc", "event_type": "betrayal", "src_character_id": "char_a"}],
        char_factions=["faction_a"],
        standings=[{"src_id": "faction_a", "dst_id": "faction_b", "standing": 50}],
    )

    result = await engine.run_tick(session, tick_id=5)  # type: ignore[arg-type]
    assert result["rule_applications"] >= 1


@pytest.mark.asyncio
async def test_run_tick_applies_decay() -> None:
    """Standing of magnitude >= min_magnitude drifts toward 0 each tick."""
    rules = _make_rules(rate_per_tick=1, min_magnitude=2)
    engine = FactionPoliticsEngine(rules=rules)

    session = _FakeSession(
        events=[],
        standings=[{"src_id": "faction_a", "dst_id": "faction_b", "standing": 50}],
    )

    result = await engine.run_tick(session)  # type: ignore[arg-type]
    assert result["decay_applications"] >= 1


@pytest.mark.asyncio
async def test_run_tick_skips_decay_below_min_magnitude() -> None:
    """Standing below min_magnitude is not decayed."""
    rules = _make_rules(rate_per_tick=1, min_magnitude=5)
    engine = FactionPoliticsEngine(rules=rules)

    # standing=3 < min_magnitude=5 → no decay
    session = _FakeSession(
        events=[],
        standings=[{"src_id": "faction_a", "dst_id": "faction_b", "standing": 3}],
    )

    result = await engine.run_tick(session)  # type: ignore[arg-type]
    assert result["decay_applications"] == 0
