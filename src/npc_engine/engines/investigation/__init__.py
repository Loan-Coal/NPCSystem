"""
Package: investigation
Layer: engines
Purpose: Detective/Mystery investigation engine for Phase 7.1.
Does NOT: expose HTTP routes or manage tick scheduling.
Dependencies injected: None (engines are constructed in dependency_singletons).
Public surface: InvestigationEngine
"""

from npc_engine.engines.investigation.investigation_engine import InvestigationEngine

__all__ = ["InvestigationEngine"]
