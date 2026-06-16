"""
Module: proactive_tick_adapter
Layer: engines
Purpose: Tick-scheduler adapter for ProactiveDialogueEngine.
         Calls get_collocated_pairs(), collects TriggerCandidates from all pairs,
         routes to the single highest-priority winner via trigger_router, generates
         a line for the winner, and enqueues it into the injected ProactiveQueue (F1.2).
         Returns {"proactive_lines": [<winner serialised>]} (or [] if nothing fired).
         Caps pair processing to MAX_PROACTIVE_CHECKS_PER_TICK per tick.
Does NOT: run Cypher directly or hold a Neo4j session; co-location reads go through the
          injected PlayerLocationReadPort.
Dependencies: engines.proactive_dialogue.proactive_engine.ProactiveDialogueEngine,
              engines.proactive_dialogue.trigger_router,
              engines.proactive_dialogue.proactive_queue (optional, injected),
              engines.ports.player_location_read_port.PlayerLocationReadPort
Dependencies injected: ProactiveDialogueEngine, PlayerLocationReadPort, ProactiveQueue (via __init__).
Used by: scheduler.tick_scheduler (wired via dependencies_engines.py)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from npc_engine.engines.proactive_dialogue.models import ProactiveLine, ProactiveTrigger
from npc_engine.engines.proactive_dialogue.proactive_engine import ProactiveDialogueEngine
from npc_engine.engines.proactive_dialogue.proactive_queue import ProactiveQueue
from npc_engine.engines.proactive_dialogue.trigger_router import (
    TriggerCandidate,
    TriggerSource,
    select_trigger,
)

if TYPE_CHECKING:
    from npc_engine.engines.ports.player_location_read_port import PlayerLocationReadPort

# Maximum (npc, player) pairs evaluated per scheduler tick.
MAX_PROACTIVE_CHECKS_PER_TICK: int = 20

# TriggerSource value for proactive-memory triggers (only live source today).
_MEMORY_SOURCE: TriggerSource = "memory"

_logger = logging.getLogger(__name__)


class ProactiveDialogueTick:
    """Tick-scheduler adapter wiring ProactiveDialogueEngine into the clock loop.

    See module docstring for full flow.  No state beyond injected deps — safe
    for concurrent use.
    """

    def __init__(
        self,
        engine: ProactiveDialogueEngine,
        location_reader: PlayerLocationReadPort,
        proactive_queue: ProactiveQueue | None = None,
    ) -> None:
        """Initialise with injected dependencies.

        Args:
            engine: Configured ProactiveDialogueEngine instance.
            location_reader: PlayerLocationReadPort for co-location queries (sessionless).
            proactive_queue: Optional ProactiveQueue; when supplied the winning
                line is enqueued for the target player (F1.2). Default None
                preserves backward-compatible behaviour for existing callers.
        """
        self._engine = engine
        self._location_reader = location_reader
        self._queue = proactive_queue

    async def run_tick(self, tick_id: int, **_: Any) -> dict[str, Any]:
        """Run proactive checks for all co-located pairs and return the winner.

        Args:
            tick_id: Current game tick.
            **_: Swallows the scheduler's ``session=`` kwarg (DEC-122 / SEV-24).

        Returns:
            Dict ``{"proactive_lines": [<serialised winner>]}`` (0 or 1 item).
        """
        pairs = await self._location_reader.get_collocated_pairs()
        capped = pairs[:MAX_PROACTIVE_CHECKS_PER_TICK]
        if not capped:
            return {"proactive_lines": []}

        candidates, trigger_map = await _collect_candidates(
            engine=self._engine, pairs=capped, tick_id=tick_id
        )
        winner_candidate = select_trigger(candidates)
        if winner_candidate is None:
            _log_tick(tick_id, len(capped), 0)
            return {"proactive_lines": []}

        line = await _generate_and_enqueue(
            engine=self._engine,
            trigger=trigger_map[id(winner_candidate)],
            queue=self._queue,
        )
        _log_tick(tick_id, len(capped), 1)
        return {"proactive_lines": [line.model_dump()]}


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _log_tick(tick_id: int, pairs_checked: int, lines_generated: int) -> None:
    """Emit a structured log entry for a completed proactive tick."""
    _logger.info(
        "proactive_tick_done",
        extra={
            "tick_id": tick_id,
            "pairs_checked": pairs_checked,
            "lines_generated": lines_generated,
        },
    )


async def _generate_and_enqueue(
    *,
    engine: ProactiveDialogueEngine,
    trigger: ProactiveTrigger,
    queue: ProactiveQueue | None,
) -> ProactiveLine:
    """Generate a line for *trigger* and optionally enqueue it.

    Args:
        engine: ProactiveDialogueEngine instance.
        trigger: Winning ProactiveTrigger from the router.
        queue: Injected ProactiveQueue (None → skip enqueue).

    Returns:
        The generated ProactiveLine.
    """
    line = await engine.generate_line(trigger)
    if queue is not None:
        await queue.enqueue(trigger.player_id, line)
    return line


async def _collect_candidates(
    *,
    engine: ProactiveDialogueEngine,
    pairs: list[tuple[str, str]],
    tick_id: int,
) -> tuple[list[TriggerCandidate], dict[int, ProactiveTrigger]]:
    """Check each pair and return routing candidates + trigger map.

    Args:
        engine: ProactiveDialogueEngine for check_trigger calls.
        pairs: Capped list of (npc_id, player_id) pairs.
        tick_id: Current game tick.

    Returns:
        Tuple of (candidates list, {id(candidate): ProactiveTrigger}).
    """
    candidates: list[TriggerCandidate] = []
    trigger_map: dict[int, ProactiveTrigger] = {}
    for npc_id, player_id in pairs:
        trigger = await engine.check_trigger(
            npc_id=npc_id, player_id=player_id, tick_id=tick_id
        )
        if trigger is None:
            continue
        candidate = TriggerCandidate(
            source=_MEMORY_SOURCE,
            priority=trigger.memory_vividness,
            payload=trigger.memory_id,
        )
        candidates.append(candidate)
        trigger_map[id(candidate)] = trigger
    return candidates, trigger_map
