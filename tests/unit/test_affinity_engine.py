"""
test_affinity_engine.py - Unit tests for derive_phase and PhaseTransition.

Does NOT: perform I/O, call the graph, or invoke LLM services.

Dependencies injected: None (pure function under test).
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Phase changes on threshold crossing
# ---------------------------------------------------------------------------


def test_phase_changes_on_threshold_crossing_stranger_to_acquaintance() -> None:
    """derive_phase returns a transition when scalars cross ACQUAINTANCE band."""
    from npc_engine.engines.relationship.affinity_engine import (
        RelationshipPhase,
        derive_phase,
    )

    result = derive_phase(
        trust=25,
        fear=0,
        affection=10,
        current_phase=RelationshipPhase.STRANGER,
        tick=5,
    )
    assert result is not None
    assert result.new_phase == RelationshipPhase.ACQUAINTANCE
    assert result.tick == 5


def test_phase_unchanged_returns_none() -> None:
    """derive_phase returns None when computed phase matches current_phase."""
    from npc_engine.engines.relationship.affinity_engine import (
        RelationshipPhase,
        derive_phase,
    )

    result = derive_phase(
        trust=0,
        fear=0,
        affection=0,
        current_phase=RelationshipPhase.STRANGER,
        tick=1,
    )
    assert result is None


def test_phase_changes_to_friend() -> None:
    """derive_phase returns FRIEND transition when composite score crosses FRIEND band."""
    from npc_engine.engines.relationship.affinity_engine import (
        RelationshipPhase,
        derive_phase,
    )

    result = derive_phase(
        trust=60,
        fear=0,
        affection=20,
        current_phase=RelationshipPhase.ACQUAINTANCE,
        tick=10,
    )
    assert result is not None
    assert result.new_phase == RelationshipPhase.FRIEND
    assert result.tick == 10


def test_phase_changes_to_hostile() -> None:
    """derive_phase returns HOSTILE transition when fear dominates."""
    from npc_engine.engines.relationship.affinity_engine import (
        RelationshipPhase,
        derive_phase,
    )

    result = derive_phase(
        trust=0,
        fear=80,
        affection=0,
        current_phase=RelationshipPhase.ACQUAINTANCE,
        tick=3,
    )
    assert result is not None
    assert result.new_phase == RelationshipPhase.HOSTILE


def test_phase_changes_to_rival() -> None:
    """derive_phase returns RIVAL transition on mid-range fear with some trust."""
    from npc_engine.engines.relationship.affinity_engine import (
        RelationshipPhase,
        derive_phase,
    )

    result = derive_phase(
        trust=10,
        fear=55,
        affection=0,
        current_phase=RelationshipPhase.ACQUAINTANCE,
        tick=7,
    )
    assert result is not None
    assert result.new_phase == RelationshipPhase.RIVAL


def test_phase_transition_model_fields() -> None:
    """PhaseTransition exposes new_phase and tick as typed fields."""
    from npc_engine.engines.relationship.affinity_engine import (
        PhaseTransition,
        RelationshipPhase,
    )

    transition = PhaseTransition(new_phase=RelationshipPhase.CLOSE, tick=42)
    assert transition.new_phase == RelationshipPhase.CLOSE
    assert transition.tick == 42


def test_close_phase_on_high_trust_and_affection() -> None:
    """derive_phase returns CLOSE when trust + affection are both very high."""
    from npc_engine.engines.relationship.affinity_engine import (
        RelationshipPhase,
        derive_phase,
    )

    result = derive_phase(
        trust=90,
        fear=0,
        affection=80,
        current_phase=RelationshipPhase.FRIEND,
        tick=20,
    )
    assert result is not None
    assert result.new_phase == RelationshipPhase.CLOSE
