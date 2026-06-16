"""Unit tests for EventHandler over the EventGraphPort (SEV-24 events slice).

Does NOT: connect to Neo4j. Both graph ports are mocked; the engine holds no session.

Tests:
  - run_tick forwards faction_id/reputation_delta + the high-severity world condition
    to emit_event_atomic, and builds the disruption routine-override plans.
  - run_tick swallows the scheduler's ignored session= kwarg.
  - run_tick skips creation when severity exceeds the world max_event_severity cap.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.events.event_handler import EventHandler
from npc_engine.engines.events.event_pool import EventTemplate


def _make_settings() -> MagicMock:
    s = MagicMock()
    s.EVENT_POOL_PATH = "unused"
    s.EVENT_RNG_SEED = 42
    s.WITNESSED_MAX_PER_EVENT = 10
    s.WORLD_ID = "world"
    return s


def _make_handler(
    templates: list[EventTemplate],
    *,
    event_repo: MagicMock,
    world_state_repo: MagicMock,
    disruption_rules: list | None = None,
) -> EventHandler:
    handler = EventHandler.__new__(EventHandler)
    handler._settings = _make_settings()
    handler._embedding_index = MagicMock()
    handler._registry = MagicMock()
    handler._registry.node_models = {"event": MagicMock(return_value=MagicMock())}
    handler._templates = templates
    handler._rng = None
    handler._lock = asyncio.Lock()
    handler._disruption_rules = disruption_rules or []
    handler._event_repo = event_repo
    handler._world_state_repo = world_state_repo
    return handler


def _template(**kwargs) -> EventTemplate:
    defaults = dict(
        id="evt_test",
        weight=1,
        severity=50,
        location_tag="keep",
        summary_template="A test event.",
        event_type="military",
    )
    defaults.update(kwargs)
    return EventTemplate.model_validate(defaults)


def _event_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_locations_by_tag = AsyncMock(return_value=["loc-1"])
    repo.emit_event_atomic = AsyncMock()
    repo.get_characters_at_location = AsyncMock(return_value=[])
    repo.record_witnesses = AsyncMock()
    repo.record_causation = AsyncMock()
    return repo


def _world_state_repo(max_severity: int = 100) -> MagicMock:
    repo = MagicMock()
    repo.get_world_state = AsyncMock(return_value=MagicMock(max_event_severity=max_severity))
    return repo


@pytest.mark.asyncio
async def test_run_tick_forwards_faction_to_emit() -> None:
    template = _template(faction_id="city_guard", reputation_delta=-10)
    repo = _event_repo()
    handler = _make_handler([template], event_repo=repo, world_state_repo=_world_state_repo())

    result = await handler.run_tick(tick_id=1)

    assert result["created"] == 1
    repo.emit_event_atomic.assert_awaited_once()
    kwargs = repo.emit_event_atomic.call_args.kwargs
    assert kwargs["faction_id"] == "city_guard"
    assert kwargs["reputation_delta"] == -10
    assert kwargs["world_condition_event_type"] is None  # severity 50 < threshold
    assert kwargs["routine_overrides"] == []


@pytest.mark.asyncio
async def test_run_tick_high_severity_sets_world_condition() -> None:
    template = _template(severity=90)
    repo = _event_repo()
    handler = _make_handler([template], event_repo=repo, world_state_repo=_world_state_repo())

    await handler.run_tick(tick_id=2)

    kwargs = repo.emit_event_atomic.call_args.kwargs
    assert kwargs["world_condition_event_type"] == "military"


@pytest.mark.asyncio
async def test_run_tick_ignores_session_kwarg() -> None:
    template = _template()
    repo = _event_repo()
    handler = _make_handler([template], event_repo=repo, world_state_repo=_world_state_repo())

    result = await handler.run_tick(session=object(), tick_id=3)

    assert result["created"] == 1


@pytest.mark.asyncio
async def test_run_tick_skips_when_over_severity_cap() -> None:
    template = _template(severity=90)
    repo = _event_repo()
    handler = _make_handler(
        [template], event_repo=repo, world_state_repo=_world_state_repo(max_severity=50)
    )

    result = await handler.run_tick(tick_id=4)

    assert result == {"tick_id": 4, "created": 0}
    repo.emit_event_atomic.assert_not_awaited()
