"""
Module: dependencies_advanced.politics
Layer: api
Purpose: Singleton factory providers for political/faction engines —
         treaty, oath, succession, agenda, military.
Does NOT: create session-scoped or per-request dependencies, or call LLM clients.
Dependencies injected: none (engines below are stateless or stub).
Dependencies: engines.treaty, engines.oath, engines.succession, engines.agenda, engines.military.
Used by: api.dependencies_advanced (package re-exporter).
"""

from __future__ import annotations

from functools import lru_cache


@lru_cache
def get_treaty_engine():
    """Create singleton treaty engine for treaty lifecycle management.

    Returns:
        TreatyEngine instance.
    """
    from npc_engine.engines.treaty.treaty_engine import TreatyEngine

    return TreatyEngine()


@lru_cache
def get_oath_engine():
    """Create singleton oath engine for pledge lifecycle management.

    Returns:
        OathEngine instance.
    """
    from npc_engine.engines.oath.oath_engine import OathEngine

    return OathEngine()


@lru_cache
def get_succession_engine():
    """Create singleton succession engine for political title inheritance.

    Returns:
        SuccessionEngine instance.
    """
    from npc_engine.engines.succession.succession_engine import SuccessionEngine

    return SuccessionEngine()


@lru_cache
def get_agenda_engine():
    """Create singleton agenda engine for political vote resolution.

    Returns:
        AgendaEngine instance.
    """
    from npc_engine.engines.agenda.agenda_engine import AgendaEngine

    return AgendaEngine()


@lru_cache
def get_military_engine():
    """Create singleton military engine (stub) for Strategy/4X tick processing.

    Returns:
        MilitaryEngine instance (no-op stub — see ISSUES.md ISSUE-001).
    """
    from npc_engine.engines.military.military_engine import MilitaryEngine

    return MilitaryEngine()
