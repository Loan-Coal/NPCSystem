"""
Regression tests for Wave 5 of SEV-24: engines/ must be free of neo4j session coupling.

All tests are initially FAILING (red) before the implementation; the implementation
makes them pass (green). Tests serve as the guard that the migration is complete.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

# ---------------------------------------------------------------------------
# scheme_detection_tick — must accept an injected port, not direct graph calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheme_detection_tick_port_injection() -> None:
    """SchemeDetectionTick accepts a scheming_repo port and uses it."""
    from types import SimpleNamespace

    from npc_engine.engines.investigation.scheme_detection_tick import SchemeDetectionTick

    settings = SimpleNamespace(
        SCHEME_DETECTION_TICK_INTERVAL=1,
        SCHEME_DISCOVERY_MIN_STEPS=2,
    )
    mock_repo = AsyncMock()
    mock_repo.get_discoverable_scheme_ids.return_value = ["s1", "s2"]
    mock_repo.mark_scheme_discovered.return_value = True

    adapter = SchemeDetectionTick(settings=settings, scheming_repo=mock_repo)
    result = await adapter.run_tick(tick_id=7)

    assert result["discovered"] == 2
    assert result["skipped"] is False
    mock_repo.get_discoverable_scheme_ids.assert_awaited_once_with(2)
    mock_repo.mark_scheme_discovered.assert_any_await("s1")
    mock_repo.mark_scheme_discovered.assert_any_await("s2")


@pytest.mark.asyncio
async def test_scheme_detection_tick_run_tick_no_session_required() -> None:
    """run_tick accepts no session kwarg (Wave 5 — session coupling fully removed)."""
    from types import SimpleNamespace

    from npc_engine.engines.investigation.scheme_detection_tick import SchemeDetectionTick

    settings = SimpleNamespace(
        SCHEME_DETECTION_TICK_INTERVAL=5,
        SCHEME_DISCOVERY_MIN_STEPS=1,
    )
    mock_repo = AsyncMock()
    mock_repo.get_discoverable_scheme_ids.return_value = []
    adapter = SchemeDetectionTick(settings=settings, scheming_repo=mock_repo)

    result = await adapter.run_tick(tick_id=10)
    assert result["tick_id"] == 10


# ---------------------------------------------------------------------------
# director_tick — must work without a session kwarg
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_director_tick_run_tick_no_session_required() -> None:
    """DirectorTick.run_tick works with only tick_id; no session needed."""
    from npc_engine.engines.director.director_tick import DirectorTick

    loc_reader = AsyncMock()
    loc_reader.get_collocated_pairs.return_value = []
    rel_reader = AsyncMock()
    event_handler = AsyncMock()

    adapter = DirectorTick(
        location_reader=loc_reader,
        relation_reader=rel_reader,
        event_handler=event_handler,
    )
    result = await adapter.run_tick(tick_id=42)
    assert "director_beats" in result


@pytest.mark.asyncio
async def test_director_tick_calls_event_handler_without_session() -> None:
    """When a beat fires, event_handler.run_tick is called WITHOUT a session kwarg."""
    from npc_engine.engines.director.director_tick import DirectorTick
    from npc_engine.engines.director.director_engine import DirectorDecision
    from unittest.mock import patch, AsyncMock as AM

    loc_reader = AsyncMock()
    loc_reader.get_collocated_pairs.return_value = [("npc1", "player1")]
    loc_reader.get_player_idle_ticks.return_value = 10
    rel_reader = AsyncMock()
    rel_reader.get_relation_scalars.return_value = {
        "trust": 60, "affection": 50, "fear": 10,
    }
    event_handler = AsyncMock()
    event_handler.run_tick.return_value = {"tick_id": 1}

    adapter = DirectorTick(
        location_reader=loc_reader,
        relation_reader=rel_reader,
        event_handler=event_handler,
    )

    with patch(
        "npc_engine.engines.director.director_tick.decide",
        return_value=DirectorDecision(should_inject=True, beat_kind="tension_escalation", reason="test"),
    ):
        await adapter.run_tick(tick_id=1)

    # event_handler.run_tick must NOT receive a session kwarg
    call_kwargs = event_handler.run_tick.call_args.kwargs
    assert "session" not in call_kwargs


# ---------------------------------------------------------------------------
# No neo4j imports survive in engines/ (compile-time check via import)
# ---------------------------------------------------------------------------


def test_awareness_seeder_file_deleted() -> None:
    """engines/events/awareness_seeder.py must be gone."""
    import importlib.util

    spec = importlib.util.find_spec("npc_engine.engines.events.awareness_seeder")
    assert spec is None, "awareness_seeder.py should have been deleted"


def test_location_scoper_file_deleted() -> None:
    """engines/events/location_scoper.py must be gone."""
    import importlib.util

    spec = importlib.util.find_spec("npc_engine.engines.events.location_scoper")
    assert spec is None, "location_scoper.py should have been deleted"


def test_edge_updater_file_deleted() -> None:
    """engines/gossip/edge_updater.py must be gone."""
    import importlib.util

    spec = importlib.util.find_spec("npc_engine.engines.gossip.edge_updater")
    assert spec is None, "edge_updater.py should have been deleted"
