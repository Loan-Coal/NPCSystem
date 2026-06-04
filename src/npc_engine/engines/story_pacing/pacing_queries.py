"""
Module: pacing_queries
Layer: engines
Purpose: Backward-compatibility re-exports; Cypher constants now live in graph.story_pacing_queries.
         This file will be removed once all callers import directly from graph.
Does NOT: define any new constants or execute queries.
Dependencies: graph.story_pacing_queries
Dependencies injected: none
Used by: (legacy callers only — no active imports as of SEV-04 story_pacing migration)
"""
from __future__ import annotations

from npc_engine.graph.story_pacing_queries import (  # noqa: F401
    CYPHER_GET_ACTIVE_HIGH_SEVERITY_QUESTS,
    CYPHER_GET_RECENT_MAJOR_EVENTS,
)
