"""
Module: director_engine
Layer: engines
Purpose: Pure decision function that, given engagement signals (player idle ticks,
         relationship phase, plateau ticks), decides whether to inject a story beat
         and which kind — returning a typed DirectorDecision or None.
Does NOT: call the graph, call the LLM, spawn tasks, or mutate any shared state.
          All graph reads must happen in the caller; signals are passed in as plain values.
          Does NOT wire into the scheduler (slice 2 concern).
Dependencies injected: None — this is a pure function module; no I/O dependencies.
Used by: (slice 2) scheduler tick; (tests) tests/unit/test_director_engine.py
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from npc_engine.engines.relationship.standing import Standing

# ---------------------------------------------------------------------------
# Beat kind registry — the canonical set of injectable beat types.
# Add new beat types here and nowhere else (OCP: new-file or extend this list).
# ---------------------------------------------------------------------------

BEAT_KINDS = (
    "re_engage_idle",
    "relationship_catalyst",
    "tension_escalation",
    "warmth_moment",
)

BeatKind = Literal["re_engage_idle", "relationship_catalyst", "tension_escalation", "warmth_moment"]

# ---------------------------------------------------------------------------
# Threshold constants — no magic numbers in the decision function.
# ---------------------------------------------------------------------------

IDLE_INJECT_THRESHOLD_TICKS: int = 10
"""Player idle tick count above which the director considers injecting a beat."""

PLATEAU_INJECT_THRESHOLD_TICKS: int = 20
"""Relationship plateau tick count above which the director injects a catalyst beat."""

HOSTILE_STANDING_ALWAYS_INJECT: bool = True
"""When the relationship phase is HOSTILE, always inject a tension-escalation beat."""


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------


class DirectorDecision(BaseModel):
    """Typed result returned by the drama director when it decides to inject a beat.

    Attributes:
        should_inject: Always True when a DirectorDecision is returned (vs None = skip).
        beat_kind: One of the recognised beat type literals.
        reason: Human-readable explanation used for logging and debug replay.
    """

    should_inject: bool
    beat_kind: BeatKind
    reason: str


# ---------------------------------------------------------------------------
# Pure decision function
# ---------------------------------------------------------------------------


def decide(
    *,
    player_idle_ticks: int,
    relationship_phase: Standing,
    relationship_plateau_ticks: int = 0,
) -> DirectorDecision | None:
    """Decide whether to inject a story beat given current engagement signals.

    The function is deterministic and side-effect-free: the same inputs always
    produce the same output.  All graph reads must be done by the caller before
    this function is invoked.

    Injection rules (evaluated in priority order):
    1. HOSTILE standing → ``tension_escalation`` beat unconditionally.
    2. Player idle > IDLE_INJECT_THRESHOLD_TICKS → ``re_engage_idle`` beat.
    3. Plateau ticks > PLATEAU_INJECT_THRESHOLD_TICKS → ``relationship_catalyst`` beat.
    4. Otherwise → None (no beat).

    Args:
        player_idle_ticks: Number of consecutive ticks the player has not acted.
        relationship_phase: Current Standing phase of the key NPC→player relationship.
        relationship_plateau_ticks: Consecutive ticks the relationship has not changed
            Standing band.  Defaults to 0 (unknown / not a plateau).

    Returns:
        A DirectorDecision when a beat should be injected, or None to stay silent.
    """
    if HOSTILE_STANDING_ALWAYS_INJECT and relationship_phase is Standing.HOSTILE:
        return DirectorDecision(
            should_inject=True,
            beat_kind="tension_escalation",
            reason=f"relationship_phase={relationship_phase.value} triggers escalation",
        )

    if player_idle_ticks > IDLE_INJECT_THRESHOLD_TICKS:
        return DirectorDecision(
            should_inject=True,
            beat_kind="re_engage_idle",
            reason=(
                f"player_idle_ticks={player_idle_ticks} "
                f"exceeds threshold={IDLE_INJECT_THRESHOLD_TICKS}"
            ),
        )

    if relationship_plateau_ticks > PLATEAU_INJECT_THRESHOLD_TICKS:
        return DirectorDecision(
            should_inject=True,
            beat_kind="relationship_catalyst",
            reason=(
                f"plateau_ticks={relationship_plateau_ticks} "
                f"exceeds threshold={PLATEAU_INJECT_THRESHOLD_TICKS}"
            ),
        )

    return None
