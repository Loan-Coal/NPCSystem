"""
Module: treaty_port
Layer: engines
Purpose: Structural Protocol for the treaty graph domain (find expiring treaties, expire
         them, list active treaties, check mechanical violation conditions), so
         TreatyEngine depends on an abstraction instead of importing treaty_queries/
         treaty_service and holding a Neo4j session. Implemented in
         graph/repositories/treaty_repository.py.
Does NOT: open sessions, run Cypher, evaluate treaties with an LLM, or import the graph layer.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.treaty.treaty_engine; implemented structurally by
         npc_engine.graph.repositories.treaty_repository.Neo4jTreatyRepository.
"""

from __future__ import annotations

from typing import Protocol


class TreatyGraphPort(Protocol):
    """Graph operations required by TreatyEngine (treaty lifecycle + condition checks)."""

    async def get_expiring_treaties(self, *, tick_id: int) -> list[str]:
        """Return ids of active treaties at or past their expiry tick."""
        ...

    async def expire_treaty(self, *, treaty_id: str, tick_id: int) -> None:
        """Mark a treaty expired at the given tick."""
        ...

    async def get_all_active_treaty_ids(self) -> list[str]:
        """Return ids of all currently active treaties."""
        ...

    async def check_treaty_conditions_mechanical(
        self, *, treaty_id: str, tick_id: int
    ) -> list[str]:
        """Return descriptions of mechanically-violated conditions for a treaty."""
        ...
