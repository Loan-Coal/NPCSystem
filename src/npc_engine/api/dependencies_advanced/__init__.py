"""
Package: dependencies_advanced
Layer: api
Purpose: Per-engine-family singleton factory providers for optional/advanced engines,
         split into cohesive submodules (politics, social, progression) by DEC-115.
Does NOT: define factories itself — re-exports the public get_* names from submodules.
Dependencies injected: none (re-exporter only; submodules inject infra/store singletons).
Public surface: get_treaty_engine, get_oath_engine, get_succession_engine, get_agenda_engine,
                get_military_engine, get_clique_formation_engine, get_mood_contagion_engine,
                get_need_decay_engine, get_negotiation_store, get_skill_progression_engine,
                get_chapter_engine, get_investigation_engine, get_memory_consolidation_engine.
Used by: api.dependency_singletons, api.dependencies_engines, api.routes.investigations.
"""

from __future__ import annotations

from npc_engine.api.dependencies_advanced.politics import (
    get_agenda_engine,
    get_military_engine,
    get_oath_engine,
    get_succession_engine,
    get_treaty_engine,
)
from npc_engine.api.dependencies_advanced.progression import (
    get_chapter_engine,
    get_investigation_engine,
    get_memory_consolidation_engine,
    get_skill_progression_engine,
)
from npc_engine.api.dependencies_advanced.social import (
    get_clique_formation_engine,
    get_mood_contagion_engine,
    get_need_decay_engine,
    get_negotiation_store,
)

__all__ = [
    "get_agenda_engine",
    "get_chapter_engine",
    "get_clique_formation_engine",
    "get_investigation_engine",
    "get_memory_consolidation_engine",
    "get_military_engine",
    "get_mood_contagion_engine",
    "get_need_decay_engine",
    "get_negotiation_store",
    "get_oath_engine",
    "get_skill_progression_engine",
    "get_succession_engine",
    "get_treaty_engine",
]
