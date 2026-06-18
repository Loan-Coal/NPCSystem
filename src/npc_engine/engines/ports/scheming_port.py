"""
Module: scheming_port
Layer: engines
Purpose: Structural Protocol for the scheming graph domain — read active schemes and
         scheme progress, look up NPC location, upsert/advance schemes, emit one
         covert scheme-step Event atomically, and detect discoverable schemes.
         SchemingEngine, SchemeAdvanceTick, and SchemeDetectionTick all depend on
         this Protocol (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, apply rules, or call LLMs.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.scheming.scheming_engine.SchemingEngine;
         npc_engine.engines.scheming.scheme_advance_tick.SchemeAdvanceTick;
         npc_engine.engines.investigation.scheme_detection_tick.SchemeDetectionTick;
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

    async def get_discoverable_scheme_ids(self, min_steps: int) -> list[str]:
        """Return active scheme IDs ripe for discovery (witnessed + enough steps).

        A scheme is discoverable when it has at least ``min_steps`` covert steps and
        its owner shares a location with another character.

        Args:
            min_steps: Minimum SCHEME_STEP count before a scheme can be discovered.

        Returns:
            List of discoverable scheme IDs (may be empty).
        """
        ...

    async def mark_scheme_discovered(self, scheme_id: str) -> bool:
        """Flip an active scheme's status to 'discovered' (idempotent, schema-free).

        Only an 'active' scheme transitions; calling on an already-discovered or
        missing scheme is a no-op.

        Args:
            scheme_id: Scheme node ID to mark discovered.

        Returns:
            True if the scheme transitioned active→discovered, else False.
        """
        ...
