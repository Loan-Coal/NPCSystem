"""
Module: director_tick
Layer: engines
Purpose: Tick-scheduler adapter that gates event-engine beat injection on the drama
         director's decide() signal (F1.5). For each co-located (npc, player) pair it
         reads idle ticks and relationship standing, calls the pure decide() function, and
         on the first pair that returns a DirectorDecision emits a world event via the
         injected EventHandler. Returns metadata records for observability.
Does NOT: call LLMs directly, write graph nodes, change event_type enums, or inject
          beat_kind into Event nodes. Beat metadata is purely in the returned dict + logs.
Dependencies injected: PlayerLocationReadPort, RelationReadPort, EventHandler (via __init__).
Note: reads go through the injected ports (no session); director STILL receives the
      scheduler session purely to forward to event_handler until the events slice migrates
      (DEC-122 / SEV-24) — do not drop the session param yet.
Used by: scheduler.tick_scheduler (wired via dependencies_engines.py).
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncSession

from npc_engine.engines.director.director_engine import (
    DirectorDecision,
    decide,
)
from npc_engine.engines.director.director_beat_log import DirectorBeatLog, DirectorBeatRecord
from npc_engine.engines.ports.player_location_read_port import PlayerLocationReadPort
from npc_engine.engines.ports.relation_read_port import RelationReadPort
from npc_engine.engines.relationship.standing import Standing, derive_standing
from npc_engine.utils.errors import RelationEdgeNotFoundError

# Maximum co-located (npc, player) pairs evaluated per scheduler tick.
MAX_DIRECTOR_CHECKS_PER_TICK: int = 20

_logger = logging.getLogger(__name__)


class DirectorTick:
    """Tick adapter wiring the drama director into the clock loop.

    On each ``run_tick``: fetches co-located pairs (capped), derives standing and idle
    count for each, calls the pure decide() function, and on the FIRST pair that returns
    a DirectorDecision emits a world event via the injected EventHandler. Subsequent
    pairs in the same tick are skipped once a beat fires (one beat per tick).

    No mutable state beyond injected dependencies — safe for concurrent use.
    """

    def __init__(
        self,
        location_reader: PlayerLocationReadPort,
        relation_reader: RelationReadPort,
        event_handler: Any,
        beat_log: DirectorBeatLog | None = None,
    ) -> None:
        """Initialise with injected dependencies.

        Args:
            location_reader: PlayerLocationReadPort for co-location and idle-tick queries.
            relation_reader: RelationReadPort for RELATES_TO scalar reads.
            event_handler: EventHandler (any object with async run_tick(session, tick_id)).
            beat_log: Optional DirectorBeatLog; when supplied, each fired beat is recorded
                for the API director-beat read surface (F2.4). Default None preserves
                backward-compatible behaviour for existing callers/tests.
        """
        self._location_reader = location_reader
        self._relation_reader = relation_reader
        self._event_handler = event_handler
        self._beat_log = beat_log

    async def run_tick(self, session: AsyncSession, tick_id: int) -> dict[str, Any]:
        """Evaluate director decide() for co-located pairs; emit a beat if one fires.

        Returns dict with ``director_beats``: list of 0 or 1 beat records, each
        containing ``beat_kind``, ``reason``, ``npc_id``, ``player_id``, ``event``.

        Args:
            session: Active Neo4j async session (forwarded only to the event handler).
            tick_id: Current game tick.
        """
        pairs = await self._location_reader.get_collocated_pairs()
        capped = pairs[:MAX_DIRECTOR_CHECKS_PER_TICK]
        beats: list[dict[str, Any]] = []

        for npc_id, player_id in capped:
            beat = await _decide_for_pair(
                relation_reader=self._relation_reader,
                location_reader=self._location_reader,
                npc_id=npc_id, player_id=player_id, tick_id=tick_id,
            )
            if beat is not None:
                record = await _emit_beat(
                    session=session, event_handler=self._event_handler,
                    tick_id=tick_id, npc_id=npc_id, player_id=player_id, decision=beat,
                )
                beats.append(record)
                await self._record_beat(decision=beat, npc_id=npc_id, player_id=player_id, tick_id=tick_id)
                break  # one beat per tick — stop after first match

        _logger.info("director_tick_done", extra={
            "tick_id": tick_id, "pairs_checked": len(capped), "beats_fired": len(beats),
        })
        return {"director_beats": beats}

    async def _record_beat(
        self, *, decision: DirectorDecision, npc_id: str, player_id: str, tick_id: int
    ) -> None:
        """Record a fired beat into the shared beat log when one is injected (F2.4)."""
        if self._beat_log is None:
            return
        await self._beat_log.record(DirectorBeatRecord(
            beat_kind=decision.beat_kind, reason=decision.reason,
            npc_id=npc_id, player_id=player_id, tick=tick_id,
        ))


# ---------------------------------------------------------------------------
# Helpers (extracted to keep run_tick and outer loop ≤ 40 lines / ≤ 3 nesting)
# ---------------------------------------------------------------------------


async def _decide_for_pair(
    *,
    relation_reader: RelationReadPort,
    location_reader: PlayerLocationReadPort,
    npc_id: str,
    player_id: str,
    tick_id: int,
) -> DirectorDecision | None:
    """Derive standing and idle count for one pair; return decide() result or None.

    On RelationEdgeNotFoundError, defaults to Standing.NEUTRAL (no crash).

    Args:
        relation_reader: RelationReadPort for RELATES_TO scalar reads.
        location_reader: PlayerLocationReadPort for idle-tick queries.
        npc_id: NPC character ID.
        player_id: Player character ID.
        tick_id: Current game tick.

    Returns:
        DirectorDecision if the director wants to inject a beat, otherwise None.
    """
    try:
        scalars = await relation_reader.get_relation_scalars(src_id=npc_id, dst_id=player_id)
        standing = derive_standing(**scalars)
    except RelationEdgeNotFoundError:
        standing = Standing.NEUTRAL

    idle = await location_reader.get_player_idle_ticks(
        npc_id=npc_id, player_id=player_id, tick_id=tick_id
    )
    return decide(player_idle_ticks=idle, relationship_phase=standing)


async def _emit_beat(
    *,
    session: AsyncSession,
    event_handler: Any,
    tick_id: int,
    npc_id: str,
    player_id: str,
    decision: DirectorDecision,
) -> dict[str, Any]:
    """Invoke the event engine and build the beat record dict.

    beat_kind/reason are metadata only — NOT written as Event.event_type
    (enum-validated; no schema change needed here).

    Args:
        session: Active Neo4j async session.
        event_handler: EventHandler with async run_tick(session, tick_id).
        tick_id: Current game tick.
        npc_id: NPC character ID that triggered the beat.
        player_id: Player character ID co-located with the NPC.
        decision: The DirectorDecision returned by decide().
    """
    event_result = await event_handler.run_tick(session=session, tick_id=tick_id)
    _logger.info("director_beat_emitted", extra={
        "tick_id": tick_id, "npc_id": npc_id, "player_id": player_id,
        "beat_kind": decision.beat_kind, "reason": decision.reason,
    })
    return {
        "beat_kind": decision.beat_kind,
        "reason": decision.reason,
        "npc_id": npc_id,
        "player_id": player_id,
        "event": event_result,
    }
