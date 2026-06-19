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
    """Mutable clock with async lock for safe concurrent access."""

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
