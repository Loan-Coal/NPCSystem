"""
Module: event_port
Layer: engines
Purpose: Structural Protocol for the event graph domain — resolve locations by tag, emit
         one event atomically (the run_in_tx unit-of-work lives in the adapter), read
         characters at a location, and record witnesses/causation. EventHandler depends on
         this Protocol instead of importing graph writers or holding a Neo4j session
         (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, select templates, or match disruption rules.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.events.event_handler.EventHandler; implemented structurally by
         npc_engine.graph.repositories.event_repository.Neo4jEventRepository.
"""

from __future__ import annotations

from typing import Protocol

from npc_engine.graph.event.event_emission_service import RoutineOverridePlan
from npc_engine.graph.event.event_writer import _EventNode


class EventGraphPort(Protocol):
    """Reads + writes the event domain needs (atomic emit + witness/causation records)."""

    async def get_locations_by_tag(self, *, location_tag: str) -> list[str]:
        """Return location ids carrying the given location tag."""
        ...

    async def emit_event_atomic(
        self,
        *,
        event: _EventNode,
        event_id: str,
        location_id: str,
        tick_id: int,
        faction_id: str | None,
        reputation_delta: int | None,
        routine_overrides: list[RoutineOverridePlan],
        world_condition_event_type: str | None,
        world_id: str,
    ) -> None:
        """Persist the event and its side effects in a single atomic transaction."""
        ...

    async def get_characters_at_location(self, *, location_id: str) -> list[str]:
        """Return ids of active characters at the location."""
        ...

    async def record_witnesses(
        self,
        *,
        witness_ids: list[str],
        subject_id: str,
        event_id: str,
        action_type: str,
        tick: int,
        clarity: int,
        interpretation: str,
    ) -> None:
        """Record a WITNESSED edge from each witness to the subject for the event."""
        ...

    async def record_causation(
        self,
        *,
        effect_node_id: str,
        effect_node_type: str,
        cause_event_id: str,
        causation_strength: int,
        cause_type: str,
        tick_lag: int,
    ) -> None:
        """Record a CAUSED_BY edge from an effect node to its cause event."""
        ...
