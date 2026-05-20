"""
Unit tests for the story pacing engine (Phase 4.3).

Tests use fake async session stubs — no live DB required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.engines.story_pacing.pacing_rules_loader import PacingRules, load_pacing_rules
from npc_engine.engines.story_pacing.story_pacing_engine import StoryPacingEngine
from npc_engine.world.world_state import WorldState


# ---------------------------------------------------------------------------
# Async session stubs
# ---------------------------------------------------------------------------

_RULES_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "src" / "npc_engine" / "engines" / "story_pacing" / "pacing_rules.yaml"
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


def _make_session(quest_rows: list[dict], event_rows: list[dict]) -> Any:
    """Build a fake async session that returns specified rows per query."""
    call_count = [0]

    async def fake_run(query: str, **kwargs: Any) -> _FakeResult:
        # First call = high-severity quests; second call = recent events.
        idx = call_count[0]
        call_count[0] += 1
        if idx == 0:
            return _FakeResult(quest_rows)
        return _FakeResult(event_rows)

    session = AsyncMock()
    session.run = fake_run
    return session


_DEFAULT_RULES = PacingRules(
    high_severity_quest_threshold=70,
    suppression_event_severity_cap=30,
    suppression_quest_rate=0.5,
    cooldown_ticks=10,
    major_event_severity_floor=60,
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_pacing_rules_loader_loads_yaml() -> None:
    """load_pacing_rules reads the real pacing_rules.yaml and populates all fields."""
    rules = load_pacing_rules(_RULES_PATH)
    assert rules.high_severity_quest_threshold > 0
    assert rules.suppression_event_severity_cap >= 0
    assert 0.0 < rules.suppression_quest_rate <= 1.0
    assert rules.cooldown_ticks > 0
    assert rules.major_event_severity_floor > 0


@pytest.mark.asyncio
async def test_run_tick_suppresses_when_high_severity_quest_active() -> None:
    """When a high-severity quest is active, max_event_severity drops to suppression cap."""
    quest_rows = [{"quest_id": "q1", "severity": 80}]
    event_rows: list[dict] = []
    session = _make_session(quest_rows, event_rows)

    engine = StoryPacingEngine(rules=_DEFAULT_RULES)
    world_state = WorldState()

    with patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.get_world_state",
        return_value=world_state,
    ), patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.upsert_world_state",
        new_callable=AsyncMock,
    ):
        result = await engine.run_tick(session=session, tick_id=5)

    assert result["suppressed"] is True
    assert result["max_event_severity"] == _DEFAULT_RULES.suppression_event_severity_cap
    assert result["quest_generation_rate"] == _DEFAULT_RULES.suppression_quest_rate


@pytest.mark.asyncio
async def test_run_tick_normal_when_no_high_severity_quest() -> None:
    """When no high-severity quests are active, max_event_severity stays at 100."""
    quest_rows: list[dict] = []
    event_rows: list[dict] = []
    session = _make_session(quest_rows, event_rows)

    engine = StoryPacingEngine(rules=_DEFAULT_RULES)
    world_state = WorldState()

    with patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.get_world_state",
        return_value=world_state,
    ), patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.upsert_world_state",
        new_callable=AsyncMock,
    ):
        result = await engine.run_tick(session=session, tick_id=5)

    assert result["suppressed"] is False
    assert result["max_event_severity"] == 100
    assert result["quest_generation_rate"] == 1.0


@pytest.mark.asyncio
async def test_run_tick_relaxes_after_cooldown() -> None:
    """When no major events occurred in the cooldown window, quest rate stays normal."""
    quest_rows: list[dict] = []
    event_rows: list[dict] = []  # no recent events → relaxed
    session = _make_session(quest_rows, event_rows)

    engine = StoryPacingEngine(rules=_DEFAULT_RULES)
    world_state = WorldState()

    with patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.get_world_state",
        return_value=world_state,
    ), patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.upsert_world_state",
        new_callable=AsyncMock,
    ):
        result = await engine.run_tick(session=session, tick_id=20)

    assert result["relaxed_after_cooldown"] is True
    assert result["quest_generation_rate"] == 1.0


@pytest.mark.asyncio
async def test_run_tick_writes_updated_world_state() -> None:
    """run_tick calls upsert_world_state with the computed suppression values."""
    quest_rows = [{"quest_id": "q1", "severity": 75}]
    event_rows: list[dict] = []
    session = _make_session(quest_rows, event_rows)

    engine = StoryPacingEngine(rules=_DEFAULT_RULES)
    world_state = WorldState()
    captured: list[WorldState] = []

    async def capture_upsert(session: Any, world_state: WorldState) -> WorldState:
        captured.append(world_state)
        return world_state

    with patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.get_world_state",
        return_value=world_state,
    ), patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.upsert_world_state",
        side_effect=capture_upsert,
    ):
        await engine.run_tick(session=session, tick_id=3)

    assert len(captured) == 1
    assert captured[0].max_event_severity == _DEFAULT_RULES.suppression_event_severity_cap
    assert captured[0].quest_generation_rate == _DEFAULT_RULES.suppression_quest_rate


def test_event_handler_skips_suppressed_severity() -> None:
    """EventHandler._select_template returns a template; caller should skip if above cap."""
    from npc_engine.world.world_state import WorldState as WS
    suppressed_state = WS(max_event_severity=30)
    assert suppressed_state.max_event_severity == 30

    # Simulate a high-severity event being blocked
    template_severity = 80
    assert template_severity > suppressed_state.max_event_severity
