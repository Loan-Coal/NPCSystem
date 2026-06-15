"""
Module: political_port
Layer: engines
Purpose: Structural Protocol for the political graph domain (titles, heirs, succession;
         extended by the agenda/faction-politics engines as they migrate). Lets the
         political engines depend on an abstraction instead of importing
         political_queries/political_*_writer and holding a Neo4j session. Implemented
         in graph/repositories/political_repository.py.
Does NOT: open sessions, run Cypher, decide succession, or import the graph layer.
Dependencies injected: none (pure interface).
Used by: npc_engine.engines.succession.succession_engine (and future political engines);
         implemented structurally by
         npc_engine.graph.repositories.political_repository.Neo4jPoliticalRepository.
"""

from __future__ import annotations

from typing import Any, Protocol


class PoliticalGraphPort(Protocol):
    """Graph operations for the political domain required by the succession engine."""

    async def get_vacant_inheritable_titles(self) -> list[dict[str, Any]]:
        """Return inheritable titles that currently have no holder."""
        ...

    async def get_heirs_for_character(self, *, character_id: str) -> list[dict[str, Any]]:
        """Return heirs (ordered by priority then legitimacy) for a character."""
        ...

    async def grant_title(self, *, character_id: str, title_id: str, tick: int) -> None:
        """Grant a title to a character via a HOLDS_TITLE edge at the given tick."""
        ...

    async def get_expired_open_agendas(self, *, current_tick: int) -> list[dict[str, Any]]:
        """Return open agendas whose deadline_tick is at or before the current tick."""
        ...

    async def get_agenda_votes(self, *, agenda_id: str) -> dict[str, Any]:
        """Return {"supports": [...], "opposes": [...]} vote rows for an agenda."""
        ...

    async def set_agenda_status(self, *, agenda_id: str, status: str) -> None:
        """Set an agenda's resolution status (e.g. 'passed' / 'failed')."""
        ...
