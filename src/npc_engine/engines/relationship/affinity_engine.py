"""
Module: affinity_engine
Layer: engines
Purpose: Derives a named RelationshipPhase from trust/fear/affection scalars and
         returns a PhaseTransition only when the phase changes.
Does NOT: perform I/O, call the graph, or invoke LLM services.
Dependencies injected: None (pure function, no external state).
Used by: relation_phase_writer (slice 2 call-site wiring).
"""

from __future__ import annotations

import enum

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Composite-score clamp bounds (reuse same scale as standing.py)
# ---------------------------------------------------------------------------

_CLAMP_MIN: int = -100
_CLAMP_MAX: int = 100

# ---------------------------------------------------------------------------
# Phase band threshold constants (UPPER_SNAKE — no magic numbers)
#
# Bands (half-open on the upper end, based on composite = clamp(trust+affection-fear)):
#   HOSTILE:      [CLAMP_MIN,    HOSTILE_MAX)   score < HOSTILE_MAX
#   RIVAL:        [HOSTILE_MAX,  RIVAL_MAX)     HOSTILE_MAX <= score < RIVAL_MAX
#   STRANGER:     [RIVAL_MAX,    STRANGER_MAX]  RIVAL_MAX <= score <= STRANGER_MAX
#   ACQUAINTANCE: (STRANGER_MAX, ACQUAINTANCE_MAX]
#   FRIEND:       (ACQUAINTANCE_MAX, FRIEND_MAX]
#   CLOSE:        (FRIEND_MAX, CLAMP_MAX]
# ---------------------------------------------------------------------------

_HOSTILE_MAX: int = -50
_RIVAL_MAX: int = -15
_STRANGER_MAX: int = 20
_ACQUAINTANCE_MAX: int = 60
_FRIEND_MAX: int = 85


class RelationshipPhase(str, enum.Enum):
    """Named relationship arc phases derived from the affinity composite score.

    Bands (composite = clamp(trust + affection - fear, -100, 100)):
        HOSTILE:      [-100, -50)
        RIVAL:        [-50,  -15)
        STRANGER:     [-15,   20]
        ACQUAINTANCE: ( 20,   60]
        FRIEND:       ( 60,   85]
        CLOSE:        ( 85,  100]
    """

    HOSTILE = "HOSTILE"
    RIVAL = "RIVAL"
    STRANGER = "STRANGER"
    ACQUAINTANCE = "ACQUAINTANCE"
    FRIEND = "FRIEND"
    CLOSE = "CLOSE"


class PhaseTransition(BaseModel):
    """Immutable record of a relationship phase change.

    Attributes:
        new_phase: The phase the relationship has transitioned to.
        tick: The game tick at which the transition occurred.
    """

    new_phase: RelationshipPhase
    tick: int

    model_config = {"frozen": True}


def derive_phase(
    *,
    trust: int,
    fear: int,
    affection: int,
    current_phase: RelationshipPhase,
    tick: int,
) -> PhaseTransition | None:
    """Compute relationship phase from scalars; return a transition only on change.

    Composite score: clamp(trust + affection - fear, -100, 100).
    Band boundaries use module-level _UPPER_SNAKE constants — no magic numbers.

    Args:
        trust: Raw trust scalar (any integer; clamping applied internally).
        fear: Raw fear scalar (any integer; clamping applied internally).
        affection: Raw affection scalar (any integer; clamping applied internally).
        current_phase: The relationship's existing phase to compare against.
        tick: Current game tick, recorded in the transition if a change occurs.

    Returns:
        PhaseTransition with the new phase and tick if the phase changed,
        or None if the derived phase equals current_phase.
    """
    raw = trust + affection - fear
    score = max(_CLAMP_MIN, min(_CLAMP_MAX, raw))
    new_phase = _score_to_phase(score)
    if new_phase == current_phase:
        return None
    return PhaseTransition(new_phase=new_phase, tick=tick)


def _score_to_phase(score: int) -> RelationshipPhase:
    """Map a clamped composite score to a RelationshipPhase band.

    Args:
        score: Clamped integer in [_CLAMP_MIN, _CLAMP_MAX].

    Returns:
        The RelationshipPhase corresponding to the score band.
    """
    if score < _HOSTILE_MAX:
        return RelationshipPhase.HOSTILE
    if score < _RIVAL_MAX:
        return RelationshipPhase.RIVAL
    if score <= _STRANGER_MAX:
        return RelationshipPhase.STRANGER
    if score <= _ACQUAINTANCE_MAX:
        return RelationshipPhase.ACQUAINTANCE
    if score <= _FRIEND_MAX:
        return RelationshipPhase.FRIEND
    return RelationshipPhase.CLOSE
