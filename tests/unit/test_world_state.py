"""
test_world_state.py - Unit tests for WorldState Pydantic model.

Does NOT: connect to Neo4j or any external service.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from npc_engine.world.world_state import WorldState


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_world_state_defaults():
    ws = WorldState()
    assert ws.id == "world"
    assert ws.epoch == "age_of_peace"
    assert ws.weather == "clear"
    assert ws.time_of_day == "morning"
    assert ws.faction_standings == {}
    assert ws.active_conditions == []


def test_world_state_custom_fields():
    ws = WorldState(
        id="world_2",
        epoch="age_of_war",
        faction_standings={"faction_a": 10, "faction_b": -5},
        active_conditions=["siege", "drought"],
        weather="stormy",
        time_of_day="night",
    )
    assert ws.epoch == "age_of_war"
    assert ws.faction_standings["faction_a"] == 10
    assert "siege" in ws.active_conditions
    assert ws.weather == "stormy"
    assert ws.time_of_day == "night"


def test_world_state_last_updated_at_is_datetime():
    ws = WorldState()
    assert isinstance(ws.last_updated_at, datetime)


def test_world_state_last_graph_updated_at_is_datetime():
    ws = WorldState()
    assert isinstance(ws.last_graph_updated_at, datetime)


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


def test_world_state_is_frozen():
    ws = WorldState()
    with pytest.raises(ValidationError):
        ws.epoch = "age_of_chaos"  # type: ignore[misc]


def test_world_state_faction_standings_is_dict():
    ws = WorldState(faction_standings={"guild": 50})
    assert isinstance(ws.faction_standings, dict)


def test_world_state_active_conditions_is_list():
    ws = WorldState(active_conditions=["war"])
    assert isinstance(ws.active_conditions, list)


# ---------------------------------------------------------------------------
# Custom datetime fields
# ---------------------------------------------------------------------------


def test_world_state_accepts_explicit_datetimes():
    now = datetime(2024, 6, 15, 12, 0, 0)
    ws = WorldState(last_updated_at=now, last_graph_updated_at=now)
    assert ws.last_updated_at == now
    assert ws.last_graph_updated_at == now
