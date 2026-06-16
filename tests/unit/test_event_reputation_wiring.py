"""Unit tests for event-triggered reputation adjustment (ISSUE-005 / SEV-24).

After the SEV-24 events slice the per-character reputation loop lives in
graph.event_emission_service.emit_event_atomic. These tests cover both halves:
  - The graph-service loop calls adjust_reputation_for_event once per character and
    swallows ReputationNotFoundError.
  - EventHandler forwards (or omits) faction_id/reputation_delta to the port.
No live DB required — all Neo4j calls / ports are mocked.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.events.event_handler import EventHandler
from npc_engine.engines.events.event_pool import EventTemplate
from npc_engine.graph.event_emission_service import emit_event_atomic
from npc_engine.utils.errors import ReputationNotFoundError

_SVC = "npc_engine.graph.event_emission_service"


async def _run_work(_session, work):
    """Fake run_in_tx: invoke the unit-of-work closure with a dummy tx."""
    await work(MagicMock())


def _make_settings() -> MagicMock:
    s = MagicMock()
    s.EVENT_POOL_PATH = "unused"
    s.EVENT_RNG_SEED = 42
    s.WITNESSED_MAX_PER_EVENT = 10
    s.WORLD_ID = "world"
    return s


def _make_handler(templates: list[EventTemplate]) -> EventHandler:
    handler = EventHandler.__new__(EventHandler)
    handler._settings = _make_settings()
    handler._embedding_index = MagicMock()
    handler._registry = MagicMock()
    handler._registry.node_models = {"event": MagicMock(return_value=MagicMock())}
    handler._templates = templates
    handler._rng = None
    handler._lock = asyncio.Lock()
    handler._disruption_rules = []
    repo = MagicMock()
    repo.get_locations_by_tag = AsyncMock(return_value=["loc-1"])
    repo.emit_event_atomic = AsyncMock()
    repo.get_characters_at_location = AsyncMock(return_value=[])
    repo.record_witnesses = AsyncMock()
    repo.record_causation = AsyncMock()
    handler._event_repo = repo
    ws = MagicMock()
    ws.get_world_state = AsyncMock(return_value=MagicMock(max_event_severity=100))
    handler._world_state_repo = ws
    return handler


def _faction_template(**kwargs) -> EventTemplate:
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


# ---------------------------------------------------------------------------
# graph.event_emission_service — per-character reputation loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_adjusts_reputation_per_character() -> None:
    """adjust_reputation_for_event is called once per character at the location."""
    session = AsyncMock()
    with patch(f"{_SVC}.run_in_tx", new=AsyncMock(side_effect=_run_work)), \
         patch(f"{_SVC}.upsert_event", new=AsyncMock()), \
         patch(f"{_SVC}.seed_awareness_tx", new=AsyncMock()), \
         patch(f"{_SVC}.get_characters_at_location", new=AsyncMock(return_value=["char-1", "char-2"])), \
         patch(f"{_SVC}.adjust_reputation_for_event", new=AsyncMock()) as mock_rep:
        await emit_event_atomic(
            session,
            event=MagicMock(),
            event_id="evt-1",
            location_id="loc-1",
            tick_id=1,
            faction_id="city_guard",
            reputation_delta=-10,
            routine_overrides=[],
            world_condition_event_type=None,
            world_id="world",
        )

    assert mock_rep.call_count == 2
    assert {call.kwargs["faction_id"] for call in mock_rep.call_args_list} == {"city_guard"}
    assert {call.kwargs["delta"] for call in mock_rep.call_args_list} == {-10}


@pytest.mark.asyncio
async def test_emit_skips_reputation_when_no_faction() -> None:
    """adjust_reputation_for_event is NOT called when faction_id is None."""
    session = AsyncMock()
    with patch(f"{_SVC}.run_in_tx", new=AsyncMock(side_effect=_run_work)), \
         patch(f"{_SVC}.upsert_event", new=AsyncMock()), \
         patch(f"{_SVC}.seed_awareness_tx", new=AsyncMock()), \
         patch(f"{_SVC}.get_characters_at_location", new=AsyncMock(return_value=["char-1"])), \
         patch(f"{_SVC}.adjust_reputation_for_event", new=AsyncMock()) as mock_rep:
        await emit_event_atomic(
            session,
            event=MagicMock(),
            event_id="evt-1",
            location_id="loc-1",
            tick_id=1,
            faction_id=None,
            reputation_delta=None,
            routine_overrides=[],
            world_condition_event_type=None,
            world_id="world",
        )

    mock_rep.assert_not_called()


@pytest.mark.asyncio
async def test_emit_swallows_reputation_not_found() -> None:
    """ReputationNotFoundError from a single character is caught and logged."""
    session = AsyncMock()
    with patch(f"{_SVC}.run_in_tx", new=AsyncMock(side_effect=_run_work)), \
         patch(f"{_SVC}.upsert_event", new=AsyncMock()), \
         patch(f"{_SVC}.seed_awareness_tx", new=AsyncMock()), \
         patch(f"{_SVC}.get_characters_at_location", new=AsyncMock(return_value=["char-1"])), \
         patch(f"{_SVC}.adjust_reputation_for_event", new=AsyncMock(
             side_effect=ReputationNotFoundError(character_id="char-1", faction_id="phantom"))):
        await emit_event_atomic(
            session,
            event=MagicMock(),
            event_id="evt-1",
            location_id="loc-1",
            tick_id=1,
            faction_id="phantom",
            reputation_delta=-5,
            routine_overrides=[],
            world_condition_event_type=None,
            world_id="world",
        )
    # No exception escapes — swallowed inside the loop.


# ---------------------------------------------------------------------------
# EventHandler — forwards faction fields to the port
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handler_forwards_faction_fields() -> None:
    template = _faction_template(faction_id="city_guard", reputation_delta=-10)
    handler = _make_handler([template])

    result = await handler.run_tick(tick_id=1)

    assert result["created"] == 1
    kwargs = handler._event_repo.emit_event_atomic.call_args.kwargs
    assert kwargs["faction_id"] == "city_guard"
    assert kwargs["reputation_delta"] == -10


@pytest.mark.asyncio
async def test_handler_omits_faction_when_absent() -> None:
    template = _faction_template(faction_id=None, reputation_delta=None)
    handler = _make_handler([template])

    await handler.run_tick(tick_id=1)

    kwargs = handler._event_repo.emit_event_atomic.call_args.kwargs
    assert kwargs["faction_id"] is None
    assert kwargs["reputation_delta"] is None


def test_event_template_loads_faction_fields() -> None:
    """EventTemplate parses faction_id and reputation_delta from JSON."""
    t = EventTemplate.model_validate({
        "id": "evt_test",
        "weight": 1,
        "severity": 35,
        "location_tag": "keep",
        "summary_template": "Drill.",
        "event_type": "military",
        "faction_id": "city_guard",
        "reputation_delta": 5,
    })
    assert t.faction_id == "city_guard"
    assert t.reputation_delta == 5


def test_event_template_faction_fields_default_none() -> None:
    """EventTemplate faction fields default to None when absent."""
    t = EventTemplate.model_validate({
        "id": "evt_test",
        "weight": 1,
        "severity": 35,
        "location_tag": "market",
        "summary_template": "Brawl.",
        "event_type": "brawl",
    })
    assert t.faction_id is None
    assert t.reputation_delta is None
