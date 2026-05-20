"""Unit tests for MilitaryEngine stub (Phase 7.4 Strategy/4X)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.military.military_engine import MilitaryEngine
from npc_engine.graph.military_writer import _validate_composition


@pytest.fixture
def engine() -> MilitaryEngine:
    return MilitaryEngine()


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


# ---------------------------------------------------------------------------
# Stub behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_tick_returns_skipped(engine, session):
    """run_tick returns skipped=True and a reason string (stub contract)."""
    result = await engine.run_tick(session, tick_id=1)

    assert result["skipped"] is True
    assert "reason" in result
    assert isinstance(result["reason"], str)


@pytest.mark.asyncio
async def test_run_tick_does_not_touch_session(engine, session):
    """The stub must not issue any Neo4j calls."""
    await engine.run_tick(session, tick_id=99)

    session.run.assert_not_called()


# ---------------------------------------------------------------------------
# Army composition validation (F8 fix)
# ---------------------------------------------------------------------------


def test_valid_composition_serialises_to_json():
    """A well-formed composition dict is accepted and returns a JSON string."""
    import json

    result = _validate_composition({"infantry": 100, "cavalry": 50, "siege": 20})
    parsed = json.loads(result)

    assert parsed["infantry"] == 100
    assert parsed["cavalry"] == 50
    assert parsed["siege"] == 20


def test_missing_composition_key_raises_value_error():
    """A composition dict missing a required key raises ValueError."""
    with pytest.raises(ValueError, match="missing required keys"):
        _validate_composition({"infantry": 100, "cavalry": 50})


def test_non_int_composition_value_raises_value_error():
    """A composition dict with a non-int value raises ValueError."""
    with pytest.raises(ValueError, match="must be int"):
        _validate_composition({"infantry": 100, "cavalry": 50, "siege": "twenty"})


def test_extra_keys_are_ignored():
    """Extra keys beyond the required three are silently dropped."""
    import json

    result = _validate_composition({"infantry": 10, "cavalry": 5, "siege": 2, "dragons": 1})
    parsed = json.loads(result)

    assert set(parsed.keys()) == {"infantry", "cavalry", "siege"}
