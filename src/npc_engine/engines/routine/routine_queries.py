"""
Module: routine_queries
Layer: engines
Purpose: Backward-compatibility re-exports; Cypher constants and query functions now
         live in graph.routine_queries.
         This file will be removed once all callers import directly from graph.
Does NOT: define any new constants or execute queries.
Dependencies: graph.routine_queries
Dependencies injected: none
Used by: (legacy callers — routine_engine, event_handler, dialogue_handler)
"""
from __future__ import annotations

from npc_engine.graph.routine_queries import (  # noqa: F401
    CYPHER_CLEAR_ROUTINE_OVERRIDE,
    CYPHER_GET_SCHEDULED_CHARACTERS,
    CYPHER_SET_ROUTINE_OVERRIDE,
    CYPHER_UPDATE_LOCATED_AT,
    clear_routine_override,
    get_scheduled_characters,
    set_routine_override,
    update_character_location,
)
