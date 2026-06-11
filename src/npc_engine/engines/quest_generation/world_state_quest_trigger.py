"""
Module: world_state_quest_trigger
Layer: engines
Purpose: Reads the current world-state epoch on each tick and triggers quest generation
         for the most appropriate NPC when an epoch maps to a known archetype.
Does NOT: expose HTTP routes, manage quest lifecycle, query Neo4j directly, or wire
          itself into the scheduler (slice 2 handles scheduler registration).
Dependencies: engines.quest_generation.quest_generation_engine,
              graph.event_trigger_queries, graph.world_state_reader
Dependencies injected: QuestGenerationEngine (via __init__).
Used by: npc_engine.scheduler.tick_scheduler (slice 2)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from neo4j import AsyncSession

from npc_engine.engines.quest_generation.event_quest_trigger import (
    DEFAULT_MILITARY_ARCHETYPES,
)
from npc_engine.graph.event_trigger_queries import get_any_military_npc
from npc_engine.graph.world_state_reader import get_world_state

if TYPE_CHECKING:
    from npc_engine.engines.quest_generation.quest_generation_engine import QuestGenerationEngine

_logger = logging.getLogger(__name__)

# Maps epoch name → archetype hint used to select an NPC quest-giver.
_EPOCH_ARCHETYPE_MAP: dict[str, str] = {
    "war": "military",
    "famine": "merchant",
    "plague": "healer",
}

DEFAULT_MAX_PER_TICK: int = 1


class WorldStateQuestTrigger:
    """Generates draft quests driven by the current world-state epoch.

    On each tick this engine reads ``world_state.epoch``, maps it to an NPC
    archetype category via ``_EPOCH_ARCHETYPE_MAP``, selects a representative
    NPC, and delegates to the injected ``QuestGenerationEngine`` to produce a
    draft quest.

    Idempotency is enforced via a module-level ``_last_triggered_tick`` sentinel:
    if ``run_tick`` is called more than once with the same ``tick_id`` the second
    call is a no-op.  Slice 2 may replace this with a graph-side cooldown node.
    """

    def __init__(
        self,
        generation_engine: QuestGenerationEngine,
        max_per_tick: int = DEFAULT_MAX_PER_TICK,
    ) -> None:
        """Initialise the world-state quest trigger.

        Args:
            generation_engine: Quest generation engine used to create draft quests.
            max_per_tick: Maximum number of quests to generate per tick (currently 1).
        """
        self._generation_engine = generation_engine
        self._max_per_tick = max_per_tick
        self._last_triggered_tick: str | int | None = None

    async def run_tick(self, session: AsyncSession, tick_id: str | int) -> dict[str, Any]:
        """Read world state and generate a draft quest if epoch warrants one.

        Skips generation (idempotency) when ``tick_id`` matches the last tick that
        already triggered quest generation.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick identifier (included in the return payload).

        Returns:
            Dict with ``tick_id``, ``quests_created`` (int), and ``quest_ids`` (list[str]).
        """
        if self._last_triggered_tick == tick_id:
            _logger.info(
                "world_state_quest_trigger: skipping duplicate tick",
                extra={"tick_id": tick_id},
            )
            return {"tick_id": tick_id, "quests_created": 0, "quest_ids": []}

        world_state = await get_world_state(session)
        archetype_hint = _EPOCH_ARCHETYPE_MAP.get(world_state.epoch)

        if archetype_hint is None:
            _logger.info(
                "world_state_quest_trigger: no archetype mapping for epoch",
                extra={"tick_id": tick_id, "epoch": world_state.epoch},
            )
            return {"tick_id": tick_id, "quests_created": 0, "quest_ids": []}

        quest_id = await self._generate_for_epoch(
            session, tick_id=tick_id, archetype_hint=archetype_hint, epoch=world_state.epoch
        )

        if quest_id is not None:
            self._last_triggered_tick = tick_id
            return {"tick_id": tick_id, "quests_created": 1, "quest_ids": [quest_id]}

        return {"tick_id": tick_id, "quests_created": 0, "quest_ids": []}

    async def _generate_for_epoch(
        self,
        session: AsyncSession,
        tick_id: str | int,
        archetype_hint: str,
        epoch: str,
    ) -> str | None:
        """Select an NPC for the epoch archetype and call the generation engine.

        Currently only the ``military`` archetype hint is supported via
        ``get_any_military_npc``.  Additional hint branches (merchant, healer)
        are scaffolded for slice 2 expansion.

        Args:
            session: Active Neo4j async session.
            tick_id: Current tick (attached to log entries).
            archetype_hint: Archetype category derived from the epoch mapping.
            epoch: Raw epoch string (used for logging).

        Returns:
            Quest ID string on success, or None when skipped or on failure.
        """
        npc_id = await self._pick_npc(session, archetype_hint)
        if npc_id is None:
            _logger.warning(
                "world_state_quest_trigger: no NPC found for archetype",
                extra={"tick_id": tick_id, "archetype_hint": archetype_hint, "epoch": epoch},
            )
            return None

        try:
            generated = await self._generation_engine.generate(
                session,
                quest_giver_id=npc_id,
            )
        except ValueError as exc:
            _logger.warning(
                "world_state_quest_trigger: quest generation skipped",
                extra={
                    "tick_id": tick_id,
                    "npc_id": npc_id,
                    "epoch": epoch,
                    "reason": str(exc),
                },
            )
            return None

        _logger.info(
            "world_state_quest_trigger: quest created",
            extra={
                "tick_id": tick_id,
                "npc_id": npc_id,
                "epoch": epoch,
                "quest_id": generated.quest_id,
            },
        )
        return generated.quest_id

    async def _pick_npc(self, session: AsyncSession, archetype_hint: str) -> str | None:
        """Return an NPC ID appropriate for the given archetype hint.

        Args:
            session: Active Neo4j async session.
            archetype_hint: Category string from ``_EPOCH_ARCHETYPE_MAP``.

        Returns:
            Character ID string, or None if no suitable NPC exists.
        """
        if archetype_hint == "military":
            return await get_any_military_npc(session, DEFAULT_MILITARY_ARCHETYPES)
        # Merchant and healer selection deferred to slice 2 (EXP-21 scheduler wiring).
        _logger.info(
            "world_state_quest_trigger: archetype hint not yet routed, no NPC selected",
            extra={"archetype_hint": archetype_hint},
        )
        return None
