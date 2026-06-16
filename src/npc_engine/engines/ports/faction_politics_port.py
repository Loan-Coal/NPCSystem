"""
Module: faction_politics_port
Layer: engines
Purpose: Structural Protocol for the faction-politics graph domain — read recent events,
         character faction membership, and all standings, plus commit one standing change
         (STANDS_WITH write + append-only history) atomically. FactionPoliticsEngine depends
         on this Protocol instead of importing graph queries/writers or holding a Neo4j
         session (DEC-122 / SEV-24).
Does NOT: open sessions, run Cypher, apply rules, or compute decay.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.faction_politics.faction_politics_engine.FactionPoliticsEngine;
         implemented structurally by
         npc_engine.graph.repositories.faction_politics_repository.Neo4jFactionPoliticsRepository.
"""

from __future__ import annotations

from typing import Any, Protocol


class FactionPoliticsGraphPort(Protocol):
    """Reads + the single atomic standing-change write the faction-politics engine needs."""

    async def get_recent_events(self) -> list[dict[str, str]]:
        """Return recent events that carry a src_character_id and event_type."""
        ...

    async def get_character_factions(self, *, character_id: str) -> list[str]:
        """Return active faction ids the character belongs to."""
        ...

    async def get_all_standings(self) -> list[dict[str, Any]]:
        """Return all STANDS_WITH edges as src_id/dst_id/standing dicts."""
        ...

    async def commit_standing_change(
        self,
        *,
        src_id: str,
        dst_id: str,
        new_standing: int,
        delta: int,
        tick: int,
        cause_event_id: str | None = None,
        cause_rule_id: str | None = None,
    ) -> None:
        """Persist a STANDS_WITH standing update and append its FactionStandingEvent."""
        ...
