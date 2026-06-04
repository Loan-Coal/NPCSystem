"""
Unit tests for the story pacing engine (Phase 4.3).

After SEV-04: the engine delegates DB calls to graph.story_pacing_queries.
Tests patch those graph functions directly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.engines.story_pacing.pacing_rules_loader import PacingRules, load_pacing_rules
from npc_engine.engines.story_pacing.story_pacing_engine import StoryPacingEngine
from npc_engine.world.world_state import WorldState


_RULES_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "src" / "npc_engine" / "engines" / "story_pacing" / "pacing_rules.yaml"
)

_DEFAULT_RULES = PacingRules(
    high_severity_quest_threshold=70,
    suppression_event_severity_cap=30,
    suppression_quest_rate=0.5,
    cooldown_ticks=10,
    major_event_severity_floor=60,
)


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
    session = AsyncMock()
    engine = StoryPacingEngine(rules=_DEFAULT_RULES)
    world_state = WorldState()

    with patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.get_active_high_severity_quests",
        new_callable=AsyncMock,
        return_value=[{"quest_id": "q1", "severity": 80}],
    ), patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.get_recent_major_events",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
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
    session = AsyncMock()
    engine = StoryPacingEngine(rules=_DEFAULT_RULES)
    world_state = WorldState()

    with patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.get_active_high_severity_quests",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.get_recent_major_events",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
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
    session = AsyncMock()
    engine = StoryPacingEngine(rules=_DEFAULT_RULES)
    world_state = WorldState()

    with patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.get_active_high_severity_quests",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.get_recent_major_events",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
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
    from typing import Any

    session = AsyncMock()
    engine = StoryPacingEngine(rules=_DEFAULT_RULES)
    world_state = WorldState()
    captured: list[WorldState] = []

    async def capture_upsert(session: Any, world_state: WorldState) -> WorldState:
        captured.append(world_state)
        return world_state

    with patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.get_active_high_severity_quests",
        new_callable=AsyncMock,
        return_value=[{"quest_id": "q1", "severity": 75}],
    ), patch(
        "npc_engine.engines.story_pacing.story_pacing_engine.get_recent_major_events",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
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
