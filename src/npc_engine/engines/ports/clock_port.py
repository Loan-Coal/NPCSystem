"""
Module: clock_port
Layer: engines
Purpose: Read-only structural Protocol exposing the current game tick, so engines and
         handlers can stamp graph writes with the authoritative GameClock tick without
         importing the concrete scheduler.GameClock (DIP; ISSUE-165).
Does NOT: advance or restore the clock, expose game_time_seconds or mode, open sessions,
          or import from scheduler/. The port is deliberately read-only — only
          TickScheduler and the api lifespan may mutate clock state.
Dependencies injected: none (pure interface).
Used by: engines/dialogue/dialogue_handler, engines/quest/*, api/routes/dialogue/*;
         implemented structurally by npc_engine.scheduler.game_clock.GameClock.
"""

from __future__ import annotations

from typing import Protocol


class ClockPort(Protocol):
    """Read-only access to the authoritative current game tick."""

    @property
    def current_tick(self) -> int:
        """Return the current game tick id (monotonic, starts at 0)."""
        ...
