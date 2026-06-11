"""
Module: proactive_queue
Layer: engines
Purpose: In-process per-recipient buffer for proactive dialogue lines produced
         by the tick scheduler; the API WebSocket handler drains this queue to
         push lines to connected players (DEC-098).

Does NOT:
  - make LLM calls or graph queries
  - hold a reference to any WebSocket or API object
  - import from api/, services/, retrieval/, or graph/

Dependencies injected:
  - None — ProactiveQueue is instantiated directly; callers inject it where
    needed (composition root is api/dependencies.py for the WS handler).

Used by:
  - engines.proactive_dialogue.proactive_tick_adapter (enqueue side, slice 2)
  - api.routes.dialogue_ws (drain side, slice 2)
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from npc_engine.engines.proactive_dialogue.models import ProactiveLine

# Maximum lines held per recipient before older lines are silently dropped.
# Prevents unbounded growth when no WS connection is draining the queue.
MAX_LINES_PER_RECIPIENT: int = 64


class ProactiveQueue:
    """Per-recipient async-safe buffer for ProactiveLine objects (DEC-098).

    Architecture:
        The engine layer (tick adapter) enqueues lines; the API layer (WS
        handler) drains them.  No upward dependency is introduced because
        ``api`` imports ``engines``, not the other way around.

    Concurrency:
        An ``asyncio.Lock`` guards all mutations of ``_buffers`` to serialise
        concurrent enqueue calls from multiple scheduler ticks.  ``drain()``
        replaces the recipient's list atomically under the same lock so the
        caller always receives a consistent snapshot and the buffer is cleared
        in one operation.

    Usage::

        queue = ProactiveQueue()
        # producer (scheduler tick):
        await queue.enqueue("player_42", line)
        # consumer (WS drain loop):
        lines = queue.drain("player_42")  # sync; safe to call from async ctx
    """

    def __init__(self) -> None:
        """Initialise an empty ProactiveQueue."""
        # defaultdict avoids KeyError on first access for a new recipient.
        self._buffers: defaultdict[str, list[ProactiveLine]] = defaultdict(list)
        # Lock serialises concurrent enqueue calls (multiple scheduler ticks).
        self._lock: asyncio.Lock = asyncio.Lock()

    async def enqueue(self, recipient_id: str, line: ProactiveLine) -> None:
        """Append a ProactiveLine to the buffer for *recipient_id*.

        If the buffer for *recipient_id* has reached MAX_LINES_PER_RECIPIENT
        the oldest entry is discarded before the new line is appended.

        Args:
            recipient_id: Identifies the player (or NPC) that should receive
                          this line.  Typically a ``player_id`` string.
            line: The ProactiveLine to buffer.
        """
        async with self._lock:
            buf = self._buffers[recipient_id]
            if len(buf) >= MAX_LINES_PER_RECIPIENT:
                buf.pop(0)
            buf.append(line)

    def drain(self, recipient_id: str) -> list[ProactiveLine]:
        """Return and clear all buffered lines for *recipient_id*.

        This is a **synchronous**, non-blocking call safe to invoke from an
        async context (it does not yield; it performs no I/O).  The buffer for
        *recipient_id* is empty after this call returns.

        Args:
            recipient_id: Same key used in ``enqueue``.

        Returns:
            Ordered list of ProactiveLine objects (oldest first).  Empty list
            if no lines are buffered for this recipient.
        """
        lines = self._buffers.pop(recipient_id, [])
        return list(lines)
