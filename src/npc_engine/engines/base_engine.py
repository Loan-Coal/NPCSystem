"""
base_engine.py - Defines a minimal asynchronous engine contract.
Layer: engines
Purpose: (auto-detected — review)

Does NOT: implement domain-specific engine behavior.

Dependencies injected: None.
"""
from __future__ import annotations

from typing import Any, Protocol


class BaseEngine(Protocol):
    """Structural protocol for session-scoped tick-driven engines.

    All concrete engines implement ``run_tick`` with varying keyword arguments
    (session, tick_id, game_time, time_of_day, etc.). This protocol captures the
    common structural marker — the method name — without enforcing a specific
    signature, since each engine's required parameters differ.
    """

    async def run_tick(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...
