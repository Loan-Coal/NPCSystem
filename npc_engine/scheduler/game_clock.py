"""
game_clock.py - Thread-safe game clock state with manual advance.

Does NOT: trigger engine ticks.

Dependencies injected: None.
"""

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

    def __init__(self, mode: str):
        self._tick_id = 0
        self._game_time_seconds = 0
        self._mode = mode
        self._lock = asyncio.Lock()

    async def advance(self, tick_delta: int, time_delta_seconds: int) -> ClockState:
        """Advance clock by deltas and return new state."""

        async with self._lock:
            self._tick_id += max(0, tick_delta)
            self._game_time_seconds += max(0, time_delta_seconds)
            return self.state

    @property
    def state(self) -> ClockState:
        """Return immutable clock snapshot."""

        return ClockState(
            tick_id=self._tick_id,
            game_time_seconds=self._game_time_seconds,
            mode=self._mode,
        )
