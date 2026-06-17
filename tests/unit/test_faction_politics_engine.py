"""Unit tests for the faction politics engine (Phase 4.1 / SEV-24 repository slice).

The engine now depends on a ``FactionPoliticsGraphPort`` injected via ``__init__`` and
holds no Neo4j session. Tests mock the port; no live DB or session stub is required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from npc_engine.engines.faction_politics.faction_politics_engine import FactionPoliticsEngine
from npc_engine.engines.faction_politics.rules_loader import (
    DecayConfig,
    FactionPoliticsRule,
    FactionPoliticsRules,
    load_rules,
)

_RULES_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "src" / "npc_engine" / "engines" / "faction_politics" / "rules.yaml"
)


# ---------------------------------------------------------------------------
# Fake port
# ---------------------------------------------------------------------------


class _FakePort:
    """In-memory FactionPoliticsGraphPort that records standing commits."""

    def __init__(
        self,
        *,
        events: list[dict[str, str]] | None = None,
        char_factions: list[str] | None = None,
        standings: list[dict[str, Any]] | None = None,
    ) -> None:
        self._events = events or []
        self._char_factions = char_factions or []
        self._standings = standings or []
        self.commits: list[dict[str, Any]] = []

    async def get_recent_events(self) -> list[dict[str, str]]:
        return list(self._events)

    async def get_character_factions(self, *, character_id: str) -> list[str]:
        return list(self._char_factions)

    async def get_all_standings(self) -> list[dict[str, Any]]:
        return [dict(s) for s in self._standings]

    async def commit_standing_change(
        self,
        *,
        src_id: str,
        dst_id: str,
        new_standing: int,
        delta: int,
        tick: int,
        cause_event_id: str | None = None,
        cause_rule_id: str | None = None,
    ) -> None:
        self.commits.append(
            {
                "src_id": src_id,
                "dst_id": dst_id,
                "new_standing": new_standing,
                "delta": delta,
                "tick": tick,
                "cause_event_id": cause_event_id,
                "cause_rule_id": cause_rule_id,
            }
        )


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
    port = _FakePort(
        events=[{"event_id": "evt-1", "event_type": "betrayal", "src_character_id": "char_a"}],
        char_factions=["faction_a"],
        standings=[{"src_id": "faction_a", "dst_id": "faction_b", "standing": 50}],
    )
    engine = FactionPoliticsEngine(rules=rules, repo=port)

    result = await engine.run_tick(tick_id=5)
    assert result["rule_applications"] >= 1
    assert port.commits[0]["cause_event_id"] == "evt-1"
    assert port.commits[0]["cause_rule_id"] == "betrayal"
    assert port.commits[0]["tick"] == 5


@pytest.mark.asyncio
async def test_run_tick_no_matching_rule_no_change() -> None:
    """Event type with no matching rule results in zero rule applications."""
    rules = _make_rules(rules=[("betrayal_penalty", "betrayal", -10)])
    port = _FakePort(
        events=[{"event_id": "e", "event_type": "unknown_event_xyz", "src_character_id": "char_a"}],
        char_factions=["faction_a"],
        standings=[{"src_id": "faction_a", "dst_id": "faction_b", "standing": 50}],
    )
    engine = FactionPoliticsEngine(rules=rules, repo=port)

    result = await engine.run_tick()
    assert result["rule_applications"] == 0
    # No rule-caused commit (decay may still fire on the standing of 50).
    assert all(c["cause_rule_id"] == "decay" for c in port.commits)


@pytest.mark.asyncio
async def test_run_tick_clamps_to_bounds() -> None:
    """Delta that would push standing past 100 is clamped before writing."""
    rules = _make_rules(rules=[("big_bonus", "alliance_act", 30)])
    port = _FakePort(
        events=[{"event_id": "e", "event_type": "alliance_act", "src_character_id": "char_a"}],
        char_factions=["faction_a"],
        standings=[{"src_id": "faction_a", "dst_id": "faction_b", "standing": 90}],
    )
    engine = FactionPoliticsEngine(rules=rules, repo=port)

    result = await engine.run_tick()
    assert result["rule_applications"] >= 1
    assert port.commits[0]["new_standing"] <= 100


@pytest.mark.asyncio
async def test_run_tick_clamps_negative_to_minus_100() -> None:
    """Delta that would push standing below -100 is clamped to -100."""
    rules = _make_rules(rules=[("big_penalty", "betrayal", -30)])
    port = _FakePort(
        events=[{"event_id": "e", "event_type": "betrayal", "src_character_id": "char_a"}],
        char_factions=["faction_a"],
        standings=[{"src_id": "faction_a", "dst_id": "faction_b", "standing": -80}],
    )
    engine = FactionPoliticsEngine(rules=rules, repo=port)

    result = await engine.run_tick()
    assert result["rule_applications"] >= 1
    assert port.commits[0]["new_standing"] >= -100


@pytest.mark.asyncio
async def test_run_tick_applies_decay() -> None:
    """Standing of magnitude >= min_magnitude drifts toward 0 each tick."""
    rules = _make_rules(rate_per_tick=1, min_magnitude=2)
    port = _FakePort(
        events=[],
        standings=[{"src_id": "faction_a", "dst_id": "faction_b", "standing": 50}],
    )
    engine = FactionPoliticsEngine(rules=rules, repo=port)

    result = await engine.run_tick()
    assert result["decay_applications"] >= 1
    assert port.commits[0]["cause_rule_id"] == "decay"


@pytest.mark.asyncio
async def test_run_tick_skips_decay_below_min_magnitude() -> None:
    """Standing below min_magnitude is not decayed."""
    rules = _make_rules(rate_per_tick=1, min_magnitude=5)
    port = _FakePort(
        events=[],
        standings=[{"src_id": "faction_a", "dst_id": "faction_b", "standing": 3}],
    )
    engine = FactionPoliticsEngine(rules=rules, repo=port)

    result = await engine.run_tick()
    assert result["decay_applications"] == 0
    assert port.commits == []


@pytest.mark.asyncio
async def test_run_tick_ignores_scheduler_session_kwarg() -> None:
    """The scheduler's session= kwarg is accepted and ignored (migration shim)."""
    rules = _make_rules(rules=[("betrayal_penalty", "betrayal", -10)])
    port = _FakePort(events=[], standings=[])
    engine = FactionPoliticsEngine(rules=rules, repo=port)

    result = await engine.run_tick(tick_id=2)
    assert result == {"rule_applications": 0, "decay_applications": 0}
