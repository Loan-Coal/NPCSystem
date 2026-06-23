"""
test_reputation_event_seeder.py — Unit tests for reputation_event_seeder.

Does NOT: execute graph I/O.

Dependencies injected: None (stub transaction).
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.graph.reputation.reputation_event_seeder import (
    REPUTATION_EVENT_SEVERITY,
    REPUTATION_EVENT_TYPE,
    _build_summary,
    create_reputation_event,
    seed_reputation_awareness,
)


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _FakeResult:
    async def consume(self) -> None:
        pass


class _FakeTx:
    """Minimal AsyncTransaction stub that records run() calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def run(self, query: str, **params: Any) -> _FakeResult:
        self.calls.append((query, params))
        return _FakeResult()


# ---------------------------------------------------------------------------
# _build_summary
# ---------------------------------------------------------------------------


def test_build_summary_positive_delta() -> None:
    summary = _build_summary("player_1", "merchants_guild", 20)
    assert "gained standing with" in summary
    assert "merchants_guild" in summary
    assert "+20" in summary


def test_build_summary_negative_delta() -> None:
    summary = _build_summary("player_1", "city_guard", -10)
    assert "lost standing with" in summary
    assert "city_guard" in summary
    assert "-10" in summary


def test_build_summary_zero_delta() -> None:
    # Zero is treated as a gain (>= 0 branch)
    summary = _build_summary("player_1", "thieves_guild", 0)
    assert "gained standing with" in summary


# ---------------------------------------------------------------------------
# create_reputation_event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_reputation_event_returns_event_id() -> None:
    tx = _FakeTx()
    event_id = await create_reputation_event(
        tx,
        character_id="player_1",
        faction_id="merchants_guild",
        delta=20,
        location_id="market_square",
        tick_id=5,
    )
    assert isinstance(event_id, str)
    assert len(event_id) == 36  # UUID format


@pytest.mark.asyncio
async def test_create_reputation_event_runs_one_query() -> None:
    tx = _FakeTx()
    await create_reputation_event(
        tx,
        character_id="player_1",
        faction_id="merchants_guild",
        delta=20,
        location_id="market_square",
        tick_id=5,
    )
    assert len(tx.calls) == 1


@pytest.mark.asyncio
async def test_create_reputation_event_passes_correct_params() -> None:
    tx = _FakeTx()
    event_id = await create_reputation_event(
        tx,
        character_id="player_1",
        faction_id="city_guard",
        delta=-15,
        location_id="guard_barracks",
        tick_id=10,
    )
    _, params = tx.calls[0]
    assert params["id"] == event_id
    assert params["severity"] == REPUTATION_EVENT_SEVERITY
    assert params["event_type"] == REPUTATION_EVENT_TYPE
    assert params["location_id"] == "guard_barracks"
    assert params["tick_id"] == 10
    assert params["src_character_id"] == "player_1"
    assert params["faction_id"] == "city_guard"
    assert params["reputation_delta"] == -15
    assert params["is_public"] is True


@pytest.mark.asyncio
async def test_create_reputation_event_unique_ids_each_call() -> None:
    tx = _FakeTx()
    id_a = await create_reputation_event(
        tx, character_id="p", faction_id="f", delta=10, location_id="loc", tick_id=1
    )
    id_b = await create_reputation_event(
        tx, character_id="p", faction_id="f", delta=10, location_id="loc", tick_id=1
    )
    assert id_a != id_b


# ---------------------------------------------------------------------------
# seed_reputation_awareness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_reputation_awareness_runs_one_query() -> None:
    tx = _FakeTx()
    await seed_reputation_awareness(
        tx, event_id="evt_123", location_id="tavern", tick_id=3
    )
    assert len(tx.calls) == 1


@pytest.mark.asyncio
async def test_seed_reputation_awareness_passes_correct_params() -> None:
    tx = _FakeTx()
    await seed_reputation_awareness(
        tx, event_id="evt_abc", location_id="market_square", tick_id=7
    )
    _, params = tx.calls[0]
    assert params["event_id"] == "evt_abc"
    assert params["location_id"] == "market_square"
    assert params["tick_id"] == 7
