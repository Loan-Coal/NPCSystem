"""
Tests for the drama director engine (EXP-227, slice 1).

Covers three scenarios per the brief:
  - Player idle beyond threshold → inject beat
  - Player actively engaged → None (no beat)
  - Relationship plateau → inject beat

Run: pytest tests/unit/test_director_engine.py -q
"""

from __future__ import annotations

import pytest

from npc_engine.engines.director.director_engine import (
    DirectorDecision,
    IDLE_INJECT_THRESHOLD_TICKS,
    decide,
)
from npc_engine.engines.relationship.standing import Standing


# ---------------------------------------------------------------------------
# Idle-threshold tests
# ---------------------------------------------------------------------------


def test_director_injects_on_idle() -> None:
    """Player idle beyond IDLE_INJECT_THRESHOLD_TICKS → decide returns a DirectorDecision."""
    result = decide(
        player_idle_ticks=IDLE_INJECT_THRESHOLD_TICKS + 1,
        relationship_phase=Standing.NEUTRAL,
    )
    assert result is not None
    assert isinstance(result, DirectorDecision)
    assert result.should_inject is True
    assert result.beat_kind is not None
    assert result.reason != ""


def test_director_silent_when_engaged() -> None:
    """Player active (idle_ticks below threshold, healthy relationship) → None."""
    result = decide(
        player_idle_ticks=0,
        relationship_phase=Standing.FRIENDLY,
    )
    assert result is None


# ---------------------------------------------------------------------------
# Plateau tests
# ---------------------------------------------------------------------------


def test_director_injects_on_plateau() -> None:
    """Relationship at a plateau phase (NEUTRAL with 0 idle) → inject a beat."""
    result = decide(
        player_idle_ticks=0,
        relationship_phase=Standing.NEUTRAL,
        relationship_plateau_ticks=50,
    )
    assert result is not None
    assert isinstance(result, DirectorDecision)
    assert result.should_inject is True
    assert result.beat_kind is not None


def test_director_silent_below_plateau_threshold() -> None:
    """Relationship plateau below threshold → no injection when player is also active."""
    result = decide(
        player_idle_ticks=0,
        relationship_phase=Standing.NEUTRAL,
        relationship_plateau_ticks=1,
    )
    assert result is None


def test_director_injects_hostile_standing() -> None:
    """HOSTILE standing always triggers injection regardless of idle ticks."""
    result = decide(
        player_idle_ticks=0,
        relationship_phase=Standing.HOSTILE,
    )
    assert result is not None
    assert result.should_inject is True


def test_director_decision_fields_are_typed() -> None:
    """DirectorDecision is a Pydantic model with typed beat_kind Literal."""
    result = decide(
        player_idle_ticks=IDLE_INJECT_THRESHOLD_TICKS + 1,
        relationship_phase=Standing.NEUTRAL,
    )
    assert result is not None
    # Verify beat_kind is one of the declared Literal values
    from npc_engine.engines.director.director_engine import BEAT_KINDS
    assert result.beat_kind in BEAT_KINDS
