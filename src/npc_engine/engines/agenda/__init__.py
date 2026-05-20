"""
Package: agenda
Layer: engines
Purpose: Agenda/voting engine for Phase 7.2 — resolves open agendas past their deadline.
Does NOT: expose HTTP routes or manage tick scheduling.
Dependencies injected: None (engines are constructed in dependency_singletons).
Public surface: AgendaEngine
"""

from npc_engine.engines.agenda.agenda_engine import AgendaEngine

__all__ = ["AgendaEngine"]
