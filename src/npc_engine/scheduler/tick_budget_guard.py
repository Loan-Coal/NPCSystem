"""
Module: tick_budget_guard
Layer: engines
Purpose: Sliding-window guard that enforces a per-minute LLM engine call ceiling.
Does NOT: call LLMs, advance the clock, or perform I/O.
Dependencies injected: None (uses time.monotonic for wall-clock reads).
Used by: scheduler.tick_autopilot.
"""

from __future__ import annotations

import time
from collections import deque


_WINDOW_SECONDS: int = 60


class TickBudgetGuard:
    """Enforces a per-minute ceiling on LLM engine activations.

    Maintains a sliding 60-second deque of activation timestamps. Not
    thread-safe; relies on the asyncio single-thread invariant of the
    autopilot event loop.
    """

    def __init__(self, max_per_minute: int) -> None:
        """Initialise with a per-minute activation ceiling.

        Args:
            max_per_minute: Max LLM engine activations per 60-second window.
                Clamped to a minimum of 1.
        """
        self._max_per_minute: int = max(1, max_per_minute)
        self._timestamps: deque[float] = deque()

    def _prune(self, now: float) -> None:
        cutoff = now - _WINDOW_SECONDS
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()

    def should_skip_llm(self, *, now: float | None = None) -> bool:
        """Return True if the LLM budget is exhausted for the current window.

        Args:
            now: Monotonic timestamp override (for testing). Uses time.monotonic() when None.
        Returns:
            True when LLM engines should be skipped this tick.
        """
        t = now if now is not None else time.monotonic()
        self._prune(t)
        return len(self._timestamps) >= self._max_per_minute

    def record_llm_tick(self, *, now: float | None = None) -> None:
        """Record that LLM engines were allowed to run this tick.

        Args:
            now: Monotonic timestamp override (for testing). Uses time.monotonic() when None.
        """
        t = now if now is not None else time.monotonic()
        self._timestamps.append(t)

    @property
    def remaining(self) -> int:
        """Return remaining LLM activations allowed in the current window.

        Returns:
            Count of allowed activations remaining; always >= 0.
        """
        self._prune(time.monotonic())
        return max(0, self._max_per_minute - len(self._timestamps))
