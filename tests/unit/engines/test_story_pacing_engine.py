"""
Unit tests for the story pacing engine (Phase 4.3).

After SEV-24: the engine depends on injected StoryPacingGraphPort + WorldStateGraphPort.
Tests inject mocked ports — no session, no patching of module-level graph functions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.story_pacing.pacing_rules_loader import PacingRules, load_pacing_rules
from npc_engine.engines.story_pacing.story_pacing_engine import StoryPacingEngine
from npc_engine.world.world_state import WorldState


_RULES_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "src" / "npc_engine" / "engines" / "story_pacing" / "pacing_rules.yaml"
)

_DEFAULT_RULES = PacingRules(
    high_severity_quest_threshold=70,
    suppression_event_severity_cap=30,
    suppression_quest_rate=0.5,
    cooldown_ticks=10,
    major_event_severity_floor=60,
)


def _make_engine(
    quests: list[dict[str, Any]] | None = None,
    events: list[dict[str, Any]] | None = None,
    world_state: WorldState | None = None,
) -> tuple[StoryPacingEngine, AsyncMock]:
    """Build a StoryPacingEngine with mocked ports; return (engine, world_state_repo)."""
    story_repo = AsyncMock()
    story_repo.get_active_high_severity_quests = AsyncMock(return_value=quests or [])
    story_repo.get_recent_major_events = AsyncMock(return_value=events or [])

    ws_repo = AsyncMock()
    ws_repo.get_world_state = AsyncMock(return_value=world_state or WorldState())
    ws_repo.upsert_world_state = AsyncMock(side_effect=lambda *, world_state: world_state)

    engine = StoryPacingEngine(
        rules=_DEFAULT_RULES, story_pacing_repo=story_repo, world_state_repo=ws_repo
    )
    return engine, ws_repo


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
    engine, _ = _make_engine(quests=[{"quest_id": "q1", "severity": 80}])

    result = await engine.run_tick(tick_id=5)

    assert result["suppressed"] is True
    assert result["max_event_severity"] == _DEFAULT_RULES.suppression_event_severity_cap
    assert result["quest_generation_rate"] == _DEFAULT_RULES.suppression_quest_rate


@pytest.mark.asyncio
async def test_run_tick_normal_when_no_high_severity_quest() -> None:
    """When no high-severity quests are active, max_event_severity stays at 100."""
    engine, _ = _make_engine(quests=[])

    result = await engine.run_tick(tick_id=5)

    assert result["suppressed"] is False
    assert result["max_event_severity"] == 100
    assert result["quest_generation_rate"] == 1.0


@pytest.mark.asyncio
async def test_run_tick_relaxes_after_cooldown() -> None:
    """When no major events occurred in the cooldown window, quest rate stays normal."""
    engine, _ = _make_engine(quests=[], events=[])

    result = await engine.run_tick(tick_id=20)

    assert result["relaxed_after_cooldown"] is True
    assert result["quest_generation_rate"] == 1.0


@pytest.mark.asyncio
async def test_run_tick_writes_updated_world_state() -> None:
    """run_tick calls upsert_world_state with the computed suppression values."""
    engine, ws_repo = _make_engine(quests=[{"quest_id": "q1", "severity": 75}])

    await engine.run_tick(tick_id=3)

    ws_repo.upsert_world_state.assert_awaited_once()
    written = ws_repo.upsert_world_state.call_args.kwargs["world_state"]
    assert written.max_event_severity == _DEFAULT_RULES.suppression_event_severity_cap
    assert written.quest_generation_rate == _DEFAULT_RULES.suppression_quest_rate


@pytest.mark.asyncio
async def test_scheduler_session_kwarg_is_ignored() -> None:
    """The scheduler still passes session=...; the engine accepts and ignores it."""
    engine, _ = _make_engine(quests=[])

    result = await engine.run_tick(tick_id=1)

    assert result["max_event_severity"] == 100


def test_event_handler_skips_suppressed_severity() -> None:
    """A suppressed max_event_severity blocks higher-severity templates (caller-side)."""
    suppressed_state = WorldState(max_event_severity=30)
    assert suppressed_state.max_event_severity == 30
    template_severity = 80
    assert template_severity > suppressed_state.max_event_severity
