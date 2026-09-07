"""
Module: probe_protocol
Layer: evals (eval harness — not part of src/)
Purpose: EngineProbe protocol — the per-engine measurement contract measurement-
         remediation Phase 3 formalises. A probe seeds state, drives one round of
         ticks, and reports numeric metrics plus named boolean invariants, so
         evals/probe_runner.py can run it k times and produce the same kind of
         fidelity-gated, receipted record the promoted scenarios already get from
         sequence_runner.py — but with a metric dict instead of one pass/fail bit
         (see docs/DEC-269's governing plan, Phase 3: "the one structural change:
         a probe returns a numeric metric dict, not a bool").
Dependencies: typing (Protocol), httpx (type only)
Used by: evals/probe_runner.py; per-engine probe modules (Phase 4)
Does NOT: import from src/npc_engine/, call the NPC engine directly, or advance
          ticks itself — a probe issues its own HTTP calls through the injected
          client, matching the convention evals/scenario_adapters*.py already set.
"""

from __future__ import annotations

from typing import Callable, Protocol

import httpx

# An invariant is a named, boolean, must-always-hold check against the client's
# post-drive state. Kept separate from measure()'s numeric dict per Phase 3's
# design: metrics are additive measurement, invariants are pass/fail correctness.
InvariantFn = Callable[[httpx.Client], bool]


class EngineProbe(Protocol):
    """Per-engine measurement probe: seed, drive, measure, and declare invariants.

    evals/probe_runner.py calls setup() then drive() then measure() once per
    repetition, after a fresh world reset — setup is not a one-time factory step,
    it re-seeds whatever state drive()/measure() need every time, exactly like
    reset_world demands of the promoted scenario adapters
    (evals/scenario_adapters*.py, whose make_*() factories build fresh entities
    per call for the same reason). Every declared invariant is checked once per
    repetition, against the client's post-drive state; any invariant returning
    False fails that repetition regardless of what its metrics report.

    Attributes:
        engine_name: Canonical engine key — matches TickScheduler.engine_status's
            keys and the POST /v1/clock/advance response body's per-engine keys
            (e.g. "gossip", "quest_generation").
        invariants: Named boolean checks. Keyed by name so a failing repetition
            can report which invariant broke, not just that one did.
    """

    engine_name: str
    invariants: dict[str, InvariantFn]

    def setup(self, client: httpx.Client) -> None:
        """Seed whatever state this repetition's drive/measure needs."""
        ...

    def drive(self, client: httpx.Client, ticks: int) -> None:
        """Advance the engine — typically POST /v1/clock/advance — for `ticks` ticks."""
        ...

    def measure(self, client: httpx.Client) -> dict[str, float]:
        """Return this probe's numeric metrics for the post-drive state."""
        ...
