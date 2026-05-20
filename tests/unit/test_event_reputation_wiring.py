"""
Unit tests for event-triggered reputation adjustment (ISSUE-005 fix).

Verifies that EventHandler.run_tick calls adjust_reputation_for_event for each
character at the event location when the template carries faction_id + reputation_delta.
No live DB required — all Neo4j calls are mocked.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.events.event_handler import EventHandler
from npc_engine.engines.events.event_pool import EventTemplate
from npc_engine.utils.errors import ReputationNotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _AsyncIterResult:
    """Minimal async-iterable wrapping a list of dicts (simulates Neo4j result)."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def __aiter__(self):
        return self._async_gen()

    async def _async_gen(self):
        for row in self._rows:
            rec = MagicMock()
            rec.__getitem__ = lambda s, k, _r=row: _r[k]
            yield rec

    async def single(self):
        return self._rows[0] if self._rows else None


def _make_settings():
    s = MagicMock()
    s.EVENT_POOL_PATH = "unused"
    s.EVENT_RNG_SEED = 42
    s.WITNESSED_MAX_PER_EVENT = 10
    return s


def _make_handler(templates: list[EventTemplate]):
    handler = EventHandler.__new__(EventHandler)
    handler._settings = _make_settings()
    handler._embedding_index = MagicMock()
    handler._registry = MagicMock()
    handler._registry.node_models = {"event": MagicMock(return_value=MagicMock())}
    handler._templates = templates
    handler._rng = None
    handler._lock = asyncio.Lock()
    handler._disruption_rules = []
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
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reputation_adjusted_for_characters_at_location():
    """adjust_reputation_for_event is called once per character when template has faction_id."""
    template = _faction_template(faction_id="city_guard", reputation_delta=-10)
    handler = _make_handler([template])
    session = AsyncMock()

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)

    async def _tx_run(query, **kwargs):
        if "LOCATED_AT" in query:
            return _AsyncIterResult([
                {"character_id": "char-1"},
                {"character_id": "char-2"},
            ])
        return _AsyncIterResult([])

    tx.run = AsyncMock(side_effect=_tx_run)
    session.begin_transaction = AsyncMock(return_value=tx)
    session.run = AsyncMock(return_value=_AsyncIterResult([]))

    with patch("npc_engine.engines.events.event_handler.get_world_state") as mock_ws, \
         patch("npc_engine.engines.events.event_handler.resolve_locations", new_callable=AsyncMock, return_value=["loc-1"]), \
         patch("npc_engine.engines.events.event_handler.validate_node_write", return_value={}), \
         patch("npc_engine.engines.events.event_handler.upsert_event", new_callable=AsyncMock), \
         patch("npc_engine.engines.events.event_handler.seed_awareness_tx", new_callable=AsyncMock), \
         patch("npc_engine.engines.events.event_handler.adjust_reputation_for_event", new_callable=AsyncMock) as mock_rep, \
         patch("npc_engine.engines.events.event_handler.invalidate_embedding_safely", new_callable=AsyncMock):

        mock_ws.return_value = MagicMock(max_event_severity=100)
        await handler.run_tick(session=session, tick_id=1)

    assert mock_rep.call_count == 2
    called_factions = {call.kwargs["faction_id"] for call in mock_rep.call_args_list}
    assert called_factions == {"city_guard"}
    called_deltas = {call.kwargs["delta"] for call in mock_rep.call_args_list}
    assert called_deltas == {-10}


@pytest.mark.asyncio
async def test_reputation_skipped_when_no_faction_id():
    """adjust_reputation_for_event is NOT called when template has no faction_id."""
    template = _faction_template(faction_id=None, reputation_delta=None)
    handler = _make_handler([template])
    session = AsyncMock()

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)
    tx.run = MagicMock(return_value=_AsyncIterResult([]))
    session.begin_transaction = AsyncMock(return_value=tx)
    session.run = MagicMock(return_value=_AsyncIterResult([]))

    with patch("npc_engine.engines.events.event_handler.get_world_state") as mock_ws, \
         patch("npc_engine.engines.events.event_handler.resolve_locations", new_callable=AsyncMock, return_value=["loc-1"]), \
         patch("npc_engine.engines.events.event_handler.validate_node_write", return_value={}), \
         patch("npc_engine.engines.events.event_handler.upsert_event", new_callable=AsyncMock), \
         patch("npc_engine.engines.events.event_handler.seed_awareness_tx", new_callable=AsyncMock), \
         patch("npc_engine.engines.events.event_handler.adjust_reputation_for_event", new_callable=AsyncMock) as mock_rep, \
         patch("npc_engine.engines.events.event_handler.invalidate_embedding_safely", new_callable=AsyncMock):

        mock_ws.return_value = MagicMock(max_event_severity=100)
        await handler.run_tick(session=session, tick_id=1)

    mock_rep.assert_not_called()


@pytest.mark.asyncio
async def test_reputation_not_found_is_swallowed():
    """ReputationNotFoundError is caught and logged; run_tick returns created=1."""
    template = _faction_template(faction_id="phantom_guild", reputation_delta=-5)
    handler = _make_handler([template])
    session = AsyncMock()

    tx = AsyncMock()
    tx.__aenter__ = AsyncMock(return_value=tx)
    tx.__aexit__ = AsyncMock(return_value=False)

    async def _tx_run(query, **kwargs):
        if "LOCATED_AT" in query:
            return _AsyncIterResult([{"character_id": "char-1"}])
        return _AsyncIterResult([])

    tx.run = AsyncMock(side_effect=_tx_run)
    session.begin_transaction = AsyncMock(return_value=tx)
    session.run = AsyncMock(return_value=_AsyncIterResult([]))

    with patch("npc_engine.engines.events.event_handler.get_world_state") as mock_ws, \
         patch("npc_engine.engines.events.event_handler.resolve_locations", new_callable=AsyncMock, return_value=["loc-1"]), \
         patch("npc_engine.engines.events.event_handler.validate_node_write", return_value={}), \
         patch("npc_engine.engines.events.event_handler.upsert_event", new_callable=AsyncMock), \
         patch("npc_engine.engines.events.event_handler.seed_awareness_tx", new_callable=AsyncMock), \
         patch("npc_engine.engines.events.event_handler.adjust_reputation_for_event",
               new_callable=AsyncMock,
               side_effect=ReputationNotFoundError(character_id="char-1", faction_id="phantom_guild")), \
         patch("npc_engine.engines.events.event_handler.invalidate_embedding_safely", new_callable=AsyncMock):

        mock_ws.return_value = MagicMock(max_event_severity=100)
        result = await handler.run_tick(session=session, tick_id=1)

    assert result["created"] == 1


def test_event_template_loads_faction_fields():
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


def test_event_template_faction_fields_default_none():
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
