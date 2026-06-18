"""
Package: agenda
Layer: engines
Purpose: Agenda/voting engine (Phase 7.2) and intent formation engine (Phase 14).
         Resolves expired agendas and scores proactive dialogue intents.
Does NOT: expose HTTP routes or manage tick scheduling.
Dependencies injected: None (engines are constructed in dependency_singletons).
Public surface: AgendaEngine, ConversationIntent, IntentFormationEngine
"""

from __future__ import annotations

from npc_engine.common.intent_models import ConversationIntent
from npc_engine.engines.agenda.agenda_engine import AgendaEngine
from npc_engine.engines.agenda.intent_formation_engine import IntentFormationEngine

__all__ = ["AgendaEngine", "ConversationIntent", "IntentFormationEngine"]
