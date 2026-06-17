"""
Module: event_quest_trigger
Layer: engines
Purpose: Watches for trigger events in the graph and calls the quest generator to
         produce a draft quest for the nearest military NPC.
Does NOT: expose HTTP routes, manage quest lifecycle state, query Neo4j directly, or
    hold a Neo4j session (DEC-122 / SEV-24).
Dependencies: engines.quest_generation.quest_generation_engine,
              engines.ports.quest_generation_port (EventTriggerGraphPort).
Dependencies injected: QuestGenerationEngine, EventTriggerGraphPort (via __init__).
Used by: npc_engine.scheduler.tick_scheduler
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from npc_engine.engines.ports.quest_generation_port import EventTriggerGraphPort

if TYPE_CHECKING:
    from npc_engine.engines.quest_generation.quest_generation_engine import QuestGenerationEngine

_logger = logging.getLogger(__name__)

DEFAULT_TRIGGER_EVENT_TYPES: frozenset[str] = frozenset({"war_begins", "conflict"})
DEFAULT_MILITARY_ARCHETYPES: frozenset[str] = frozenset(
    {"guard_captain", "soldier", "military_officer", "general", "commander"}
)
_MAX_EVENTS_PER_TICK: int = 10


class EventQuestTrigger:
    """Generates draft quests in response to configured trigger events on each tick.

    On each tick this engine queries for Event nodes whose ``event_type`` matches
    the configured trigger set and that do not yet have a Quest node with a
    CAUSED_BY edge pointing at them.  For each such event it selects the nearest
    military NPC (at the same location, falling back to any military NPC in the
    world) and delegates to the injected ``QuestGenerationEngine`` to produce a
    draft quest.

    The CAUSED_BY edge written by ``generate()`` acts as the idempotency guard:
    subsequent tick calls will skip events that already triggered a quest.

    Attributes:
        _trigger_repo: EventTriggerGraphPort (injected; provides trigger + NPC look-ups).
    """

    def __init__(
        self,
        generation_engine: QuestGenerationEngine,
        trigger_repo: EventTriggerGraphPort,
        trigger_event_types: frozenset[str] = DEFAULT_TRIGGER_EVENT_TYPES,
        military_archetypes: frozenset[str] = DEFAULT_MILITARY_ARCHETYPES,
    ) -> None:
        """Initialise the event quest trigger.

        Args:
            generation_engine: Quest generation engine used to create draft quests.
            trigger_repo: Graph port for unprocessed event queries and NPC look-ups.
            trigger_event_types: Event ``event_type`` values that trigger quest creation.
            military_archetypes: Character archetypes considered military for NPC selection.
        """
        self._generation_engine = generation_engine
        self._trigger_repo = trigger_repo
        self._trigger_event_types = trigger_event_types
        self._military_archetypes = military_archetypes

    async def run_tick(self, *, tick_id: int) -> dict:
        """Query for unprocessed trigger events and generate a draft quest for each.

        Args:
            tick_id: Current game tick identifier (included in the return payload).

        Returns:
            Dict with ``tick_id``, ``quests_created`` (int), and ``quest_ids`` (list[str]).
        """
        events = await self._trigger_repo.get_unprocessed_trigger_events(
            self._trigger_event_types, _MAX_EVENTS_PER_TICK
        )
        quest_ids: list[str] = []
        for event in events:
            quest_id = await self._process_event(event, tick_id)
            if quest_id is not None:
                quest_ids.append(quest_id)
        _logger.info(
            "event_quest_trigger tick",
            extra={"tick_id": tick_id, "quests_created": len(quest_ids)},
        )
        return {"tick_id": tick_id, "quests_created": len(quest_ids), "quest_ids": quest_ids}

    async def _process_event(self, event: dict, tick_id: int) -> str | None:
        """Select a military NPC for the event and generate a draft quest.

        Tries the event's location first; falls back to any military NPC in the
        world.  Returns None and logs a warning if no NPC is found or if quest
        generation fails.

        Args:
            event: Row from get_unprocessed_trigger_events (event_id, location_id).
            tick_id: Current tick (attached to log entries).

        Returns:
            Quest ID string on success, or None on failure.
        """
        event_id: str = str(event["event_id"])
        location_id: str = str(event.get("location_id") or "")

        npc_id = await self._find_military_npc(location_id)
        if npc_id is None:
            _logger.warning(
                "event_quest_trigger: no military NPC found for event",
                extra={"event_id": event_id, "tick_id": tick_id},
            )
            return None

        try:
            generated = await self._generation_engine.generate(
                quest_giver_id=npc_id,
                cause_event_id=event_id,
            )
        except ValueError as exc:
            _logger.warning(
                "event_quest_trigger: quest generation skipped",
                extra={"event_id": event_id, "npc_id": npc_id, "reason": str(exc)},
            )
            return None

        _logger.info(
            "event_quest_trigger: quest created",
            extra={"event_id": event_id, "npc_id": npc_id, "quest_id": generated.quest_id},
        )
        return generated.quest_id

    async def _find_military_npc(self, location_id: str) -> str | None:
        """Return a military NPC at the location, falling back to any military NPC.

        Args:
            location_id: Preferred location to search first.

        Returns:
            Character ID string, or None if no military NPC exists anywhere.
        """
        if location_id:
            npc_id = await self._trigger_repo.get_military_npc_at_location(
                location_id=location_id, archetypes=self._military_archetypes
            )
            if npc_id is not None:
                return npc_id
        return await self._trigger_repo.get_any_military_npc(archetypes=self._military_archetypes)
