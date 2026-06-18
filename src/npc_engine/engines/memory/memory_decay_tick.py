"""
Module: memory_decay_tick
Layer: engines
Purpose: Tick-scheduler adapter that runs scheduled forgetting-decay (F1.7): on its
         configured interval it reduces memory vividness via the charge-weighted decay,
         so low-salience, non-pinned memories fade over ticks while high-charge ones persist.
Does NOT: run Cypher directly (delegates to MemoryEngine), delete memories, or call LLMs.
Dependencies injected: MemoryEngine, interval (via __init__).
Used by: scheduler.tick_scheduler (wired via dependencies_engines.py).
"""

from __future__ import annotations

import logging
from typing import Any

from npc_engine.engines.memory.memory_engine import MemoryEngine

_logger = logging.getLogger(__name__)


class MemoryDecayTick:
    """Tick adapter that applies charge-weighted vividness decay on a fixed interval.

    Self-skips on ticks that are not a multiple of the configured interval, so the
    scheduler can call it every tick without extra gating. No mutable state beyond
    the injected dependencies — safe for concurrent use.
    """

    def __init__(self, memory_engine: MemoryEngine, interval: int) -> None:
        """Initialise with the memory engine and decay cadence.

        Args:
            memory_engine: Engine exposing ``decay_vividness_weighted()``.
            interval: Run decay every N ticks; clamped to a minimum of 1.
        """
        self._memory_engine = memory_engine
        self._interval = max(1, interval)

    async def run_tick(self, tick_id: int) -> dict[str, Any]:
        """Apply charge-weighted vividness decay when the tick is on the interval.

        Args:
            tick_id: Current game tick.
            **_: Swallows the scheduler's ``session=`` kwarg during the SEV-24
                migration; the memory engine holds its own graph port.

        Returns:
            Dict with ``memories_decayed``: number of Memory nodes decayed (0 when skipped).
        """
        if tick_id % self._interval != 0:
            return {"memories_decayed": 0}
        decayed = await self._memory_engine.decay_vividness_weighted()
        _logger.info("memory_decay_tick_done", extra={"tick_id": tick_id, "memories_decayed": decayed})
        return {"memories_decayed": decayed}
