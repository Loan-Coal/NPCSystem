"""
Module: investigation_port
Layer: engines
Purpose: Structural Protocol for the investigation graph domain (read-only evidence,
         witness, suspect, deduction, alibi, and rumor-contradiction queries) so the
         InvestigationEngine depends on one abstraction and holds no Neo4j session
         (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, detect contradictions, or import graph functions.
Dependencies injected: none (pure interface).
Used by: engines/investigation/investigation_engine; implemented structurally by
         npc_engine.graph.repositories.investigation_repository.Neo4jInvestigationRepository.
"""

from __future__ import annotations

from typing import Any, Protocol


class InvestigationGraphPort(Protocol):
    """Read-only graph access for crime-event investigation aggregation."""

    async def get_evidence_for_event(self, *, event_id: str) -> list[dict[str, Any]]:
        """Return all Evidence nodes linked to the event."""
        ...

    async def get_witnesses_of_event(self, *, event_id: str) -> list[dict[str, Any]]:
        """Return all WITNESSED edges for the event."""
        ...

    async def get_suspects_for_event(self, *, event_id: str) -> list[dict[str, Any]]:
        """Return all SUSPECTS edges linked to the event."""
        ...

    async def get_deductions_for_character(
        self, *, character_id: str
    ) -> list[dict[str, Any]]:
        """Return all Deduction nodes held by the investigator."""
        ...

    async def get_contradicting_rumors(self, *, event_id: str) -> list[dict[str, Any]]:
        """Return CONTRADICTS-linked Rumor pairs about the event."""
        ...

    async def get_alibi_window(
        self, *, character_id: str, from_tick: int, to_tick: int
    ) -> list[dict[str, Any]]:
        """Return the character's WAS_AT location history within [from_tick, to_tick]."""
        ...
