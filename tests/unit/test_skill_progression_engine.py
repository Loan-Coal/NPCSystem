"""Unit tests for SkillProgressionEngine — graph access via a mocked SkillGraphPort."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.skill.skill_progression_engine import SkillProgressionEngine


def _make_repo(rows: list[dict[str, Any]], new_level: int = 2) -> AsyncMock:
    repo = AsyncMock()
    repo.get_completed_quests_with_skills = AsyncMock(return_value=rows)
    repo.increment_xp = AsyncMock(return_value=new_level)
    return repo


def _row(character_id: str = "c1", skill_id: str = "s1", quest_id: str = "q1") -> dict[str, Any]:
    return {"character_id": character_id, "skill_id": skill_id, "quest_id": quest_id}


@pytest.mark.asyncio
async def test_awards_xp_per_completed_skill_row():
    repo = _make_repo([_row("c1", "s1"), _row("c2", "s2")])
    engine = SkillProgressionEngine(skill_repo=repo, xp_per_completion=50)

    result = await engine.run_tick(tick_id=7)

    assert result == {"xp_awards": 2}
    repo.get_completed_quests_with_skills.assert_awaited_once_with(tick_id=7)
    assert repo.increment_xp.await_count == 2
    repo.increment_xp.assert_any_await(character_id="c1", skill_id="s1", xp_delta=50, tick=7)


@pytest.mark.asyncio
async def test_no_completions_no_awards():
    repo = _make_repo([])
    engine = SkillProgressionEngine(skill_repo=repo)

    result = await engine.run_tick(tick_id=1)

    assert result == {"xp_awards": 0}
    repo.increment_xp.assert_not_called()


@pytest.mark.asyncio
async def test_increment_failure_is_swallowed_and_counted_out():
    """A failing XP write is logged and skipped; other rows still award."""
    repo = _make_repo([_row("c1", "s1"), _row("c2", "s2")])
    repo.increment_xp = AsyncMock(side_effect=[RuntimeError("boom"), 3])
    engine = SkillProgressionEngine(skill_repo=repo)

    result = await engine.run_tick(tick_id=2)

    assert result == {"xp_awards": 1}


@pytest.mark.asyncio
async def test_scheduler_session_kwarg_is_ignored():
    repo = _make_repo([_row()])
    engine = SkillProgressionEngine(skill_repo=repo)

    result = await engine.run_tick(session=object(), tick_id=4)

    assert result == {"xp_awards": 1}
