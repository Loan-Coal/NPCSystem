"""
Package: relationship
Layer: engines
Purpose: Relationship affinity engine — derives a named Standing band from raw trust/fear/affection scalars.
Does NOT: perform I/O or call LLM services; all logic is pure.
Dependencies injected: None.
Public surface: derive_standing, Standing
"""

from __future__ import annotations

from npc_engine.engines.relationship.standing import Standing, derive_standing

__all__ = ["Standing", "derive_standing"]
