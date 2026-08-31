"""
game_clock.py - Thread-safe game clock state with manual advance.
Layer: engines
Purpose: Thread-safe game clock state with manual advance.

Does NOT: trigger engine ticks.

Dependencies injected: None.
"""
from __future__ import annotations

import asyncio

from pydantic import BaseModel, ConfigDict


class ClockState(BaseModel):
    """Serializable clock state snapshot."""

    tick_id: int
    game_time_seconds: int
    mode: str

    model_config = ConfigDict(frozen=True)


class GameClock:
    """Mutable clock with async lock for safe concurrent access.

    Structurally satisfies ``engines.ports.clock_port.ClockPort`` on its read side.
    Engines depend on that Protocol, never on this class, so they can read the tick
    but cannot advance it (ISSUE-165).
    """

    def __init__(self, mode: str) -> None:
        """Initialise the clock at tick 0.

        Args:
            mode: Clock mode string (e.g. ``"manual"`` or ``"auto"``).
        """

        self._tick_id = 0
        self._game_time_seconds = 0
        self._mode = mode
        self._lock = asyncio.Lock()

    async def advance(self, tick_delta: int, time_delta_seconds: int) -> ClockState:
        """Advance the clock by the given deltas and return the new state.

        Negative deltas are clamped to zero; the clock never moves backwards.

        Args:
            tick_delta: Number of ticks to advance.
            time_delta_seconds: In-game seconds to advance.

        Returns:
            Immutable ClockState snapshot after the advance.
        """

        async with self._lock:
            self._tick_id += max(0, tick_delta)
            self._game_time_seconds += max(0, time_delta_seconds)
            return self.state

    async def restore(self, tick_id: int, game_time_seconds: int) -> ClockState:
        """Seed the clock from persisted world state at startup.

        Monotonic like advance(): takes the maximum of the current and persisted values,
        so a late or duplicate restore can never rewind a running clock, and a world whose
        node is absent (or predates ISSUE-165) hydrates to 0 as a no-op.

        Called once from the api lifespan; never from an engine — ClockPort deliberately
        does not expose it.

        Args:
            tick_id: Tick id read from the persisted WorldState.
            game_time_seconds: Elapsed in-game seconds read from the persisted WorldState.

        Returns:
            Immutable ClockState snapshot after seeding.
        """

        async with self._lock:
            self._tick_id = max(self._tick_id, tick_id)
            self._game_time_seconds = max(self._game_time_seconds, game_time_seconds)
            return self.state

    @property
    def current_tick(self) -> int:
        """Return the current tick id (satisfies engines.ports.clock_port.ClockPort)."""

        return self._tick_id

    @property
    def state(self) -> ClockState:
        """Return an immutable snapshot of the current clock state.

        Returns:
            ClockState with the current tick_id, game_time_seconds, and mode.
        """

        return ClockState(
            tick_id=self._tick_id,
            game_time_seconds=self._game_time_seconds,
            mode=self._mode,
        )
