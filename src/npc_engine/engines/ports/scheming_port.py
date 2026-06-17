"""
Module: scheming_port
Layer: engines
Purpose: Structural Protocol for the scheming graph domain — read active schemes and
         scheme progress, look up NPC location, upsert/advance schemes, and emit one
         covert scheme-step Event atomically. SchemingEngine and SchemeAdvanceTick
         depend on this Protocol instead of importing graph queries/writers or holding
         a Neo4j session (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, apply rules, or call LLMs.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.scheming.scheming_engine.SchemingEngine;
         npc_engine.engines.scheming.scheme_advance_tick.SchemeAdvanceTick;
         implemented structurally by
         npc_engine.graph.repositories.scheming_repository.Neo4jSchemingRepository.
"""

from __future__ import annotations

from typing import Any, Protocol

from npc_engine.graph.scheme_reader import ActiveSchemeProgress, SchemeRecord


class SchemingGraphPort(Protocol):
    """Reads and writes for the scheming domain — scheme lifecycle + covert steps."""

    async def get_active_schemes(self, npc_id: str) -> list[SchemeRecord]:
        """Return all active schemes for the given NPC (for cap check)."""
        ...

    async def upsert_scheme(
        self,
        *,
        scheme_id: str,
        npc_id: str,
        goal: str,
        tick: int,
    ) -> None:
        """Create or update a Scheme node and its EXECUTES_SCHEME edge."""
        ...

    async def add_scheme_step(
        self,
        *,
        scheme_id: str,
        event_id: str,
        step_order: int,
        completed: bool,
    ) -> None:
        """Create or update a SCHEME_STEP edge (non-atomic single write)."""
        ...

    async def get_all_active_schemes_with_steps(self) -> list[ActiveSchemeProgress]:
        """Return all active schemes with their current step counts."""
        ...

    async def get_npc_location_id(self, npc_id: str) -> str | None:
        """Return the location node id the NPC currently occupies, or None."""
        ...

    async def emit_scheme_step_atomic(
        self,
        *,
        event: Any,
        scheme_id: str,
        event_id: str,
        step_order: int,
        completed: bool,
    ) -> None:
        """Atomically upsert the covert Event and link it as the next SCHEME_STEP.

        Both writes must share one transaction so a failure between them cannot
        leave an orphan Event with no SCHEME_STEP link (SEV-01 / L2-07).
        """
        ...
