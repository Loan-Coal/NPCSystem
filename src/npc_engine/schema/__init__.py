"""
schema package - Runtime schema loading and helper resolvers.

Does NOT: execute graph writes.

Dependencies injected: None.
"""

from npc_engine.schema.schema_loader import load_game_schema
from npc_engine.schema.schema_models import SchemaConfig

__all__ = ["SchemaConfig", "load_game_schema"]
