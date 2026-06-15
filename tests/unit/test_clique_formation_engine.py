"""
Unit tests for engines.clique.clique_formation_engine — graph access via a mocked
GroupGraphPort (DEC-122 / SEV-24).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.clique.clique_formation_engine import CliqueFormationEngine


def _make_settings(interval: int = 5, affection: int = 70, cohesion: int = 10, stale: int = 50):
    s = MagicMock()
    s.CLIQUE_FORMATION_TICK_INTERVAL = interval
    s.CLIQUE_AFFECTION_THRESHOLD = affection
    s.CLIQUE_INITIAL_COHESION = cohesion
    s.CLIQUE_STALE_AGE_TICKS = stale
    return s


def _make_repo(
    pairs: list[dict[str, Any]] | None = None,
    existing_group: dict[str, Any] | None = None,
    stale: list[str] | None = None,
    new_group_id: str = "g1",
) -> AsyncMock:
    """Build a mock GroupGraphPort."""
    repo = AsyncMock()
    repo.get_high_affection_pairs = AsyncMock(return_value=pairs or [])
    repo.get_existing_shared_group = AsyncMock(return_value=existing_group)
    repo.get_stale_cliques = AsyncMock(return_value=stale or [])
    repo.create_group = AsyncMock(return_value=new_group_id)
    repo.add_member = AsyncMock()
    repo.dissolve_group = AsyncMock()
    return repo


def _engine(settings, repo) -> CliqueFormationEngine:
    return CliqueFormationEngine(settings=settings, group_repo=repo)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clique_engine_forwards_settings_thresholds() -> None:
    """SEV-12: affection/cohesion/stale come from settings, not module constants."""
    settings = _make_settings(interval=1, affection=88, cohesion=3, stale=7)
    pair = {"char_a_id": "a", "char_b_id": "b", "loc_a": "L", "loc_b": "L"}
    repo = _make_repo(pairs=[pair], existing_group=None)
    engine = _engine(settings, repo)

    await engine.run_tick(tick_id=10)

    assert repo.get_high_affection_pairs.await_args.kwargs["threshold"] == 88
    assert repo.create_group.await_args.kwargs["cohesion"] == 3
    assert repo.get_stale_cliques.await_args.kwargs["stale_before_tick"] == 3  # max(0, 10 - 7)


@pytest.mark.asyncio
async def test_skip_when_interval_not_met():
    repo = _make_repo()
    engine = _engine(_make_settings(interval=5), repo)
    result = await engine.run_tick(tick_id=3)
    assert result == {"skipped": True}
    repo.get_high_affection_pairs.assert_not_called()


@pytest.mark.asyncio
async def test_runs_when_interval_met_returns_keys():
    engine = _engine(_make_settings(interval=5), _make_repo())
    result = await engine.run_tick(tick_id=5)
    assert "formed" in result
    assert "dissolved" in result


@pytest.mark.asyncio
async def test_scheduler_session_kwarg_is_ignored():
    """The scheduler still passes session=...; the engine accepts and ignores it."""
    engine = _engine(_make_settings(interval=5), _make_repo())
    result = await engine.run_tick(session=object(), tick_id=5)
    assert "formed" in result


@pytest.mark.asyncio
async def test_skips_pair_different_locations():
    pairs = [{"char_a_id": "a", "char_b_id": "b", "loc_a": "loc1", "loc_b": "loc2"}]
    engine = _engine(_make_settings(interval=5), _make_repo(pairs=pairs))
    result = await engine.run_tick(tick_id=5)
    assert result["formed"] == 0


@pytest.mark.asyncio
async def test_skips_pair_none_location():
    pairs = [{"char_a_id": "a", "char_b_id": "b", "loc_a": None, "loc_b": None}]
    engine = _engine(_make_settings(interval=5), _make_repo(pairs=pairs))
    result = await engine.run_tick(tick_id=5)
    assert result["formed"] == 0


@pytest.mark.asyncio
async def test_forms_clique_for_co_located_pair():
    pairs = [{"char_a_id": "a", "char_b_id": "b", "loc_a": "loc1", "loc_b": "loc1"}]
    repo = _make_repo(pairs=pairs, existing_group=None, new_group_id="group-uuid")
    engine = _engine(_make_settings(interval=5), repo)

    result = await engine.run_tick(tick_id=5)

    assert result["formed"] == 1
    repo.create_group.assert_awaited_once()
    assert repo.add_member.await_count == 2


@pytest.mark.asyncio
async def test_skips_pair_with_existing_clique():
    pairs = [{"char_a_id": "a", "char_b_id": "b", "loc_a": "loc1", "loc_b": "loc1"}]
    repo = _make_repo(pairs=pairs, existing_group={"group_id": "existing-group"})
    engine = _engine(_make_settings(interval=5), repo)
    result = await engine.run_tick(tick_id=5)
    assert result["formed"] == 0
    repo.create_group.assert_not_called()


@pytest.mark.asyncio
async def test_dissolves_stale_cliques():
    repo = _make_repo(stale=["old-group"])
    engine = _engine(_make_settings(interval=5), repo)
    result = await engine.run_tick(tick_id=5)
    assert result["dissolved"] == 1
    repo.dissolve_group.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_double_run_across_ticks():
    """Separate tick invocations each complete independently."""
    engine = _engine(_make_settings(interval=5), _make_repo())
    r1 = await engine.run_tick(tick_id=5)
    r2 = await engine.run_tick(tick_id=10)
    assert "formed" in r1
    assert "formed" in r2
