"""
Module: proactive_tick_adapter
Layer: engines
Purpose: Tick-scheduler adapter for ProactiveDialogueEngine.
         Calls get_collocated_pairs(), collects TriggerCandidates from all pairs
         (memory, need, and event sources), routes to the single highest-priority
         winner via trigger_router, generates a line for the winner, and enqueues
         it into the injected ProactiveQueue (F1.2/ISSUE-094).
         Returns {"proactive_lines": [<winner serialised>]} (or [] if nothing fired).
         Caps pair processing to MAX_PROACTIVE_CHECKS_PER_TICK per tick.
Does NOT: run Cypher directly or hold a Neo4j session; co-location reads go through the
          injected PlayerLocationReadPort; need/event reads go through IntentGraphPort.
Dependencies: engines.proactive_dialogue.proactive_engine.ProactiveDialogueEngine,
              engines.proactive_dialogue.trigger_router,
              engines.proactive_dialogue.proactive_queue (optional, injected),
              engines.ports.player_location_read_port.PlayerLocationReadPort,
              engines.ports.intent_port.IntentGraphPort (optional, injected)
Dependencies injected: ProactiveDialogueEngine, PlayerLocationReadPort,
                       ProactiveQueue (optional), IntentGraphPort (optional) via __init__.
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
    from npc_engine.engines.ports.intent_port import IntentGraphPort
    from npc_engine.engines.ports.player_location_read_port import PlayerLocationReadPort

# Maximum (npc, player) pairs evaluated per scheduler tick.
MAX_PROACTIVE_CHECKS_PER_TICK: int = 20

# How many ticks back to look when fetching witnessed events for a proactive candidate.
RECENT_EVENT_LOOKBACK_TICKS: int = 5

# TriggerSource constants — avoid raw string literals at call sites.
_MEMORY_SOURCE: TriggerSource = "memory"
_NEED_SOURCE: TriggerSource = "need"
_EVENT_SOURCE: TriggerSource = "event"

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
        intent_repo: IntentGraphPort | None = None,
    ) -> None:
        """Initialise with injected dependencies.

        Args:
            engine: Configured ProactiveDialogueEngine instance.
            location_reader: PlayerLocationReadPort for co-location queries (sessionless).
            proactive_queue: Optional ProactiveQueue; when supplied the winning
                line is enqueued for the target player (F1.2). Default None
                preserves backward-compatible behaviour for existing callers.
            intent_repo: Optional IntentGraphPort; when supplied, adds need and event
                candidates to the router for each (npc, player) pair (ISSUE-094/DEC-136).
                Default None — no need/event candidates are generated.
        """
        self._engine = engine
        self._location_reader = location_reader
        self._queue = proactive_queue
        self._intent_repo = intent_repo

    async def run_tick(self, tick_id: int) -> dict[str, Any]:
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
            engine=self._engine,
            pairs=capped,
            tick_id=tick_id,
            intent_repo=self._intent_repo,
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
    intent_repo: IntentGraphPort | None = None,
) -> tuple[list[TriggerCandidate], dict[int, ProactiveTrigger]]:
    """Collect memory + intent candidates for all pairs; return (candidates, trigger_map)."""
    candidates: list[TriggerCandidate] = []
    trigger_map: dict[int, ProactiveTrigger] = {}
    for npc_id, player_id in pairs:
        trigger = await engine.check_trigger(
            npc_id=npc_id, player_id=player_id, tick_id=tick_id
        )
        if trigger is not None:
            candidate = TriggerCandidate(
                source=_MEMORY_SOURCE,
                priority=trigger.memory_vividness,
                payload=trigger.memory_id,
            )
            candidates.append(candidate)
            trigger_map[id(candidate)] = trigger
        if intent_repo is not None:
            cands, tmap = await _merge_intent_candidates(
                intent_repo=intent_repo,
                npc_id=npc_id,
                player_id=player_id,
                tick_id=tick_id,
            )
            candidates.extend(cands)
            trigger_map.update(tmap)
    return candidates, trigger_map


async def _merge_intent_candidates(
    *,
    intent_repo: IntentGraphPort,
    npc_id: str,
    player_id: str,
    tick_id: int,
) -> tuple[list[TriggerCandidate], dict[int, ProactiveTrigger]]:
    """Combine need + event candidates for one (npc, player) pair."""
    need_cands, need_map = await _collect_need_candidates(
        intent_repo=intent_repo, npc_id=npc_id, player_id=player_id, tick_id=tick_id,
    )
    event_cands, event_map = await _collect_event_candidates(
        intent_repo=intent_repo, npc_id=npc_id, player_id=player_id, tick_id=tick_id,
    )
    return need_cands + event_cands, {**need_map, **event_map}


async def _collect_need_candidates(
    *,
    intent_repo: IntentGraphPort,
    npc_id: str,
    player_id: str,
    tick_id: int,
) -> tuple[list[TriggerCandidate], dict[int, ProactiveTrigger]]:
    """Build need-sourced candidates from the NPC's unmet needs."""
    needs = await intent_repo.get_unmet_needs(npc_id=npc_id)
    candidates: list[TriggerCandidate] = []
    trigger_map: dict[int, ProactiveTrigger] = {}
    for need in needs:
        intensity: int = need.get("intensity", 0)
        trigger = ProactiveTrigger(
            npc_id=npc_id,
            player_id=player_id,
            tick_id=tick_id,
            reason="unmet_need",
            memory_id=need["id"],
            memory_content=need.get("label", ""),
            memory_vividness=intensity,
        )
        candidate = TriggerCandidate(
            source=_NEED_SOURCE, priority=intensity, payload=need["id"]
        )
        candidates.append(candidate)
        trigger_map[id(candidate)] = trigger
    return candidates, trigger_map


async def _collect_event_candidates(
    *,
    intent_repo: IntentGraphPort,
    npc_id: str,
    player_id: str,
    tick_id: int,
) -> tuple[list[TriggerCandidate], dict[int, ProactiveTrigger]]:
    """Build event-sourced candidates from events the NPC recently witnessed."""
    since = max(0, tick_id - RECENT_EVENT_LOOKBACK_TICKS)
    events = await intent_repo.get_witnessed_events(npc_id=npc_id, since_tick=since)
    candidates: list[TriggerCandidate] = []
    trigger_map: dict[int, ProactiveTrigger] = {}
    for event in events:
        severity: int = event.get("severity", 0)
        trigger = ProactiveTrigger(
            npc_id=npc_id,
            player_id=player_id,
            tick_id=tick_id,
            reason="witnessed_event",
            memory_id=event["id"],
            memory_content=event.get("summary", ""),
            memory_vividness=severity,
        )
        candidate = TriggerCandidate(
            source=_EVENT_SOURCE, priority=severity, payload=event["id"]
        )
        candidates.append(candidate)
        trigger_map[id(candidate)] = trigger
    return candidates, trigger_map
