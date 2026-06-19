"""
Module: director_tick
Layer: engines
Purpose: Tick-scheduler adapter that gates event-engine beat injection on the drama
         director's decide() signal (F1.5). For each co-located (npc, player) pair it
         reads idle ticks and relationship standing, calls the pure decide() function, and
         on the first pair that returns a DirectorDecision emits a world event via the
         injected EventHandler. Returns metadata records for observability.
         Maintains an in-memory plateau tracker (ISSUE-097/DEC-135): counts consecutive
         ticks at the same Standing band per (npc, player) pair; resets on band change.
Does NOT: call LLMs directly, write graph nodes, change event_type enums, or inject
          beat_kind into Event nodes. Beat metadata is purely in the returned dict + logs.
Dependencies injected: PlayerLocationReadPort, RelationReadPort, EventHandler (via __init__).
Used by: scheduler.tick_scheduler (wired via dependencies_engines.py).
"""

from __future__ import annotations

import logging
from typing import Any

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
            event_handler: EventHandler (any object with async run_tick(tick_id)).
            beat_log: Optional DirectorBeatLog; when supplied, each fired beat is recorded
                for the API director-beat read surface (F2.4). Default None preserves
                backward-compatible behaviour for existing callers/tests.

        In-memory plateau tracker (ISSUE-097/DEC-135):
            _plateau_tracker maps (npc_id, player_id) → (last_standing, consecutive_ticks).
            Counts consecutive ticks at the same Standing band; resets on band change.
            Not persisted across process restarts — acceptable because beat injection is
            idempotent and the director recovers within one full cycle of ticks.
        """
        self._location_reader = location_reader
        self._relation_reader = relation_reader
        self._event_handler = event_handler
        self._beat_log = beat_log
        self._plateau_tracker: dict[tuple[str, str], tuple[Standing, int]] = {}

    async def run_tick(self, *, tick_id: int) -> dict[str, Any]:
        """Evaluate director decide() for co-located pairs; emit a beat if one fires.

        Returns dict with ``director_beats``: list of 0 or 1 beat records, each
        containing ``beat_kind``, ``reason``, ``npc_id``, ``player_id``, ``event``.

        Args:
            tick_id: Current game tick.
        """
        pairs = await self._location_reader.get_collocated_pairs()
        capped = pairs[:MAX_DIRECTOR_CHECKS_PER_TICK]
        beats: list[dict[str, Any]] = []

        for npc_id, player_id in capped:
            key = (npc_id, player_id)
            plateau_ticks = _read_plateau(self._plateau_tracker, key)
            beat, standing = await _decide_for_pair(
                relation_reader=self._relation_reader,
                location_reader=self._location_reader,
                npc_id=npc_id, player_id=player_id, tick_id=tick_id,
                plateau_ticks=plateau_ticks,
            )
            _update_plateau(self._plateau_tracker, key, standing)
            if beat is not None:
                record = await _emit_beat(
                    event_handler=self._event_handler,
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


def _read_plateau(
    tracker: dict[tuple[str, str], tuple[Standing, int]],
    key: tuple[str, str],
) -> int:
    """Return the current plateau tick count for *key* (0 when unseen)."""
    entry = tracker.get(key)
    return entry[1] if entry is not None else 0


def _update_plateau(
    tracker: dict[tuple[str, str], tuple[Standing, int]],
    key: tuple[str, str],
    standing: Standing,
) -> None:
    """Increment the plateau counter for *key* if standing is unchanged; reset otherwise.

    On first encounter or band change, sets count=1 (one tick at this standing just happened).
    Subsequent calls at the same band increment the counter, so the next _read_plateau
    returns the number of consecutive prior ticks at this standing (including the current one).
    """
    entry = tracker.get(key)
    if entry is None or entry[0] != standing:
        tracker[key] = (standing, 1)
    else:
        tracker[key] = (standing, entry[1] + 1)


async def _decide_for_pair(
    *,
    relation_reader: RelationReadPort,
    location_reader: PlayerLocationReadPort,
    npc_id: str,
    player_id: str,
    tick_id: int,
    plateau_ticks: int = 0,
) -> tuple[DirectorDecision | None, Standing]:
    """Derive standing and idle count for one pair; return (decide() result, standing).

    On RelationEdgeNotFoundError, defaults to Standing.NEUTRAL (no crash).

    Args:
        relation_reader: RelationReadPort for RELATES_TO scalar reads.
        location_reader: PlayerLocationReadPort for idle-tick queries.
        npc_id: NPC character ID.
        player_id: Player character ID.
        tick_id: Current game tick.
        plateau_ticks: Consecutive ticks at current Standing band (from _plateau_tracker).

    Returns:
        Tuple of (DirectorDecision or None, derived Standing).
    """
    try:
        scalars = await relation_reader.get_relation_scalars(src_id=npc_id, dst_id=player_id)
        standing = derive_standing(**scalars)
    except RelationEdgeNotFoundError:
        standing = Standing.NEUTRAL

    idle = await location_reader.get_player_idle_ticks(
        npc_id=npc_id, player_id=player_id, tick_id=tick_id
    )
    decision = decide(
        player_idle_ticks=idle,
        relationship_phase=standing,
        relationship_plateau_ticks=plateau_ticks,
    )
    return decision, standing


async def _emit_beat(
    *,
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
        event_handler: EventHandler with async run_tick(tick_id).
        tick_id: Current game tick.
        npc_id: NPC character ID that triggered the beat.
        player_id: Player character ID co-located with the NPC.
        decision: The DirectorDecision returned by decide().

    Returns:
        Dict with beat_kind, reason, npc_id, player_id, event keys.
    """
    event_result = await event_handler.run_tick(tick_id=tick_id)
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
