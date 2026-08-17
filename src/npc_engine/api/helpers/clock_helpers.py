"""
Module: clock_helpers
Layer: api
Purpose: Resolve the game tick a request should be applied at, so every route shares one
         definition of what an absent tick means (ISSUE-165).
Dependencies: npc_engine.engines.ports.clock_port.
Used by: api.routes.economy, api.routes.knowledge, api.routes.faction_politics,
         api.routes.admin.
Does NOT: advance the clock, read the graph, or validate the tick against world state.
Dependencies injected: ClockPort (passed per call).
"""

from __future__ import annotations

from npc_engine.engines.ports.clock_port import ClockPort


def resolve_tick(requested: int | None, clock: ClockPort) -> int:
    """Return the game tick a request should be applied at.

    ``None`` means "now" — the authoritative clock tick. An explicit value is an
    intentional backdate, letting callers backlog events at a past tick. Before
    ISSUE-165 these fields defaulted to 0, so a caller that simply omitted the tick
    silently stamped every write with tick 0.

    Args:
        requested: Tick supplied by the caller, or None to use the current tick.
        clock: Read-only game clock providing the authoritative current tick.

    Returns:
        The tick to stamp on writes for this request.
    """
    if requested is None:
        return clock.current_tick
    return requested
