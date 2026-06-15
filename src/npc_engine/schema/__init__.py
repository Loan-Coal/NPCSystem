"""
schema package - Runtime schema loading and helper resolvers.
Layer: config
Purpose: (auto-detected — review)
Public surface: (list re-exports here)

Does NOT: execute graph writes.

Dependencies injected: None.
"""

from __future__ import annotations

from npc_engine.schema.schema_loader import load_game_schema
from npc_engine.schema.schema_models import SchemaConfig

__all__ = ["SchemaConfig", "load_game_schema"]
