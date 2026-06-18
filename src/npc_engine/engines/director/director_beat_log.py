"""
Module: director_beat_log
Layer: engines
Purpose: In-process bounded ring buffer of recent drama-director beats (F2.4). The
         director tick records a beat here when one fires; an API read route surfaces
         the recent beats so the demo can show a "something stirs" cue.
Does NOT: call the LLM, query the graph, or hold any WebSocket/API reference.
Dependencies injected: none — instantiated directly; the composition root shares one.
Used by: engines.director.director_tick (record side), api.routes.dialogue (read side).
"""

from __future__ import annotations

import asyncio
from collections import deque

from pydantic import BaseModel

# Maximum number of recent beats retained; older beats are dropped.
MAX_RECENT_BEATS: int = 32


class DirectorBeatRecord(BaseModel):
    """A single recorded director beat (metadata only; the world event is separate).

    Attributes:
        beat_kind: The DirectorDecision beat kind that fired.
        reason: Human-readable reason from the director decision.
        npc_id: NPC whose co-location triggered the beat.
        player_id: Player the beat targets.
        tick: Game tick at which the beat fired.
    """

    beat_kind: str
    reason: str
    npc_id: str
    player_id: str
    tick: int

    model_config = {"frozen": True}


class DirectorBeatLog:
    """Async-safe, bounded log of the most recent director beats.

    A single shared instance is recorded into by the director tick and read by the
    API route. Retains at most MAX_RECENT_BEATS entries (oldest dropped). An
    ``asyncio.Lock`` guards record mutations; ``recent`` is a non-blocking snapshot.
    """

    def __init__(self) -> None:
        """Initialise an empty bounded beat log."""
        self._beats: deque[DirectorBeatRecord] = deque(maxlen=MAX_RECENT_BEATS)
        self._lock: asyncio.Lock = asyncio.Lock()

    async def record(self, beat: DirectorBeatRecord) -> None:
        """Append a beat, evicting the oldest when the cap is exceeded.

        Args:
            beat: The DirectorBeatRecord to retain.
        """
        async with self._lock:
            self._beats.append(beat)

    def recent(self, limit: int) -> list[DirectorBeatRecord]:
        """Return up to ``limit`` most recent beats, newest first.

        Synchronous and non-blocking (a snapshot copy); safe from async contexts.

        Args:
            limit: Maximum number of beats to return.

        Returns:
            Newest-first list of DirectorBeatRecord (length ≤ limit).
        """
        snapshot = list(self._beats)
        snapshot.reverse()
        return snapshot[: max(0, limit)]
