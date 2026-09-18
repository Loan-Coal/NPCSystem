"""
Module: tick_llm_budget
Layer: engines
Purpose: Shared per-tick LLM invocation budget for the three quest trigger engines.
Does NOT: call LLMs, touch Neo4j, or expose HTTP routes.
Dependencies injected: none.
Used by: event_quest_trigger, need_quest_trigger, world_state_quest_trigger.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


class TickLLMBudget:
    """Shared per-tick cap on quest trigger LLM invocations.

    All three quest trigger engines share one instance injected at construction.
    The budget auto-resets when a new ``tick_id`` is observed — the first trigger
    to call ``consume_for_tick`` for a new tick resets the counter, so the object
    is safe to use as a singleton across ticks.

    Attributes:
        _max: Maximum invocations allowed per tick.
        _current_tick: The tick_id for which ``_used`` was last reset.
        _used: Number of invocations consumed in the current tick.
    """

    def __init__(self, max_invocations: int) -> None:
        """Initialise the budget.

        Args:
            max_invocations: Maximum calls to allow per tick across all triggers.
        """
        self._max: int = max_invocations
        self._current_tick: int | str | None = None
        self._used: int = 0

    def consume_for_tick(self, tick_id: int | str) -> bool:
        """Attempt to consume one invocation for the given tick.

        Resets the counter automatically when ``tick_id`` differs from the
        previous tick so the budget is always scoped to the current tick.

        Args:
            tick_id: Current tick identifier.

        Returns:
            True if the invocation is within budget and should proceed.
            False if the budget is exhausted and the caller should skip.
        """
        if tick_id != self._current_tick:
            self._current_tick = tick_id
            self._used = 0
        if self._used >= self._max:
            _logger.info(
                "quest_trigger_llm_budget_exhausted",
                extra={"tick_id": tick_id, "max_invocations": self._max, "duration_ms": 0},
            )
            return False
        self._used += 1
        return True

    @property
    def remaining(self) -> int:
        """Remaining invocations in the current tick."""
        return max(0, self._max - self._used)
