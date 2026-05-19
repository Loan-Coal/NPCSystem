"""
Unit tests for engines.clique.clique_formation_engine.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.clique.clique_formation_engine import CliqueFormationEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeRecord:
    """Minimal record that supports dict(record) via keys()/getitem()."""

    def __init__(self, data: dict):
        self._data = data

    def keys(self):
        return list(self._data.keys())

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data.items())


class _FakeCursor:
    """Async-iterable that yields FakeRecord instances."""

    def __init__(self, rows: list[dict]):
        self._rows = rows

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for row in self._rows:
            yield _FakeRecord(row)

    async def single(self):
        if self._rows:
            return _FakeRecord(self._rows[0])
        return None


def _make_settings(interval: int = 5):
    s = MagicMock()
    s.CLIQUE_FORMATION_TICK_INTERVAL = interval
    return s


def _make_session(pairs=None, existing_group=None, stale=None):
    """Build a mock AsyncSession that routes queries by their Cypher content."""
    pairs = pairs or []
    stale = stale or []

    async def _run(query, **kwargs):
        # Route by distinct keywords present in each Cypher constant
        if "affection" in query.lower() or "HIGH_AFFECTION" in query:
            return _FakeCursor(pairs)
        elif "BELONGS_TO_GROUP" in query and "kind:" in query:
            return _FakeCursor([existing_group] if existing_group is not None else [])
        elif "stale_before_tick" in query or "STALE" in query:
            return _FakeCursor(stale)
        else:
            return _FakeCursor([])

    session = MagicMock()
    session.run = AsyncMock(side_effect=_run)
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_when_interval_not_met():
    engine = CliqueFormationEngine(settings=_make_settings(interval=5))
    session = _make_session()
    result = await engine.run_tick(session=session, tick_id=3)
    assert result == {"skipped": True}
    session.run.assert_not_called()


@pytest.mark.asyncio
async def test_runs_when_interval_met_returns_keys():
    engine = CliqueFormationEngine(settings=_make_settings(interval=5))
    session = _make_session()
    result = await engine.run_tick(session=session, tick_id=5)
    assert "formed" in result
    assert "dissolved" in result


@pytest.mark.asyncio
async def test_skips_pair_different_locations():
    pairs = [{"char_a_id": "a", "char_b_id": "b", "loc_a": "loc1", "loc_b": "loc2"}]
    session = _make_session(pairs=pairs)
    engine = CliqueFormationEngine(settings=_make_settings(interval=5))
    result = await engine.run_tick(session=session, tick_id=5)
    assert result["formed"] == 0


@pytest.mark.asyncio
async def test_skips_pair_none_location():
    pairs = [{"char_a_id": "a", "char_b_id": "b", "loc_a": None, "loc_b": None}]
    session = _make_session(pairs=pairs)
    engine = CliqueFormationEngine(settings=_make_settings(interval=5))
    result = await engine.run_tick(session=session, tick_id=5)
    assert result["formed"] == 0


@pytest.mark.asyncio
async def test_forms_clique_for_co_located_pair():
    pairs = [{"char_a_id": "a", "char_b_id": "b", "loc_a": "loc1", "loc_b": "loc1"}]
    # existing=None means no shared group → should create one
    session = _make_session(pairs=pairs, existing_group=None)

    with patch(
        "npc_engine.engines.clique.clique_formation_engine.create_group",
        new_callable=AsyncMock,
        return_value="group-uuid",
    ), patch(
        "npc_engine.engines.clique.clique_formation_engine.add_member",
        new_callable=AsyncMock,
    ):
        engine = CliqueFormationEngine(settings=_make_settings(interval=5))
        result = await engine.run_tick(session=session, tick_id=5)

    assert result["formed"] == 1


@pytest.mark.asyncio
async def test_skips_pair_with_existing_clique():
    pairs = [{"char_a_id": "a", "char_b_id": "b", "loc_a": "loc1", "loc_b": "loc1"}]
    existing = {"group_id": "existing-group"}
    session = _make_session(pairs=pairs, existing_group=existing)
    engine = CliqueFormationEngine(settings=_make_settings(interval=5))
    result = await engine.run_tick(session=session, tick_id=5)
    assert result["formed"] == 0


@pytest.mark.asyncio
async def test_dissolves_stale_cliques():
    stale = [{"group_id": "old-group"}]
    session = _make_session(stale=stale)

    with patch(
        "npc_engine.engines.clique.clique_formation_engine.dissolve_group",
        new_callable=AsyncMock,
    ):
        engine = CliqueFormationEngine(settings=_make_settings(interval=5))
        result = await engine.run_tick(session=session, tick_id=5)

    assert result["dissolved"] == 1


@pytest.mark.asyncio
async def test_no_double_run_across_ticks():
    """Separate tick invocations each complete independently."""
    engine = CliqueFormationEngine(settings=_make_settings(interval=5))
    r1 = await engine.run_tick(session=_make_session(), tick_id=5)
    r2 = await engine.run_tick(session=_make_session(), tick_id=10)
    assert "formed" in r1
    assert "formed" in r2
