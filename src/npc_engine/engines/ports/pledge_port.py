"""
Module: pledge_port
Layer: engines
Purpose: Structural Protocol for the pledge graph domain (find expiring pledges, break
         them, list active pledgers, detect violations), so OathEngine depends on an
         abstraction instead of importing pledge_service/pledge_violation_service and
         holding a Neo4j session. Implemented in graph/repositories/pledge_repository.py.
Does NOT: open sessions, run Cypher, emit events, or import the graph layer.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.oath.oath_engine; implemented structurally by
         npc_engine.graph.repositories.pledge_repository.Neo4jPledgeRepository.
"""

from __future__ import annotations

from typing import Any, Protocol


class PledgeGraphPort(Protocol):
    """Graph operations required by OathEngine (pledge lifecycle + violation checks)."""

    async def get_expiring_pledges(self, *, tick_id: int) -> list[dict[str, Any]]:
        """Return pledges (pledger_id/pledgee_id/pledge_type) at/past their expiry tick."""
        ...

    async def break_pledge(
        self, *, pledger_id: str, pledgee_id: str, pledge_type: str, tick: int
    ) -> None:
        """Break a pledge between two characters at the given tick."""
        ...

    async def get_all_active_pledgers(self) -> list[str]:
        """Return ids of all characters with at least one active pledge."""
        ...

    async def check_pledge_violations(self, *, pledger_id: str, tick: int) -> list[dict[str, Any]]:
        """Return detected pledge violations for a pledger as of the given tick."""
        ...
