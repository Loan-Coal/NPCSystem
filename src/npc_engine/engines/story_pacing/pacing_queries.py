"""
Module: pacing_queries
Layer: engines
Purpose: Cypher query constants for the story pacing engine.
Does NOT: execute queries; callers pass these to Neo4j sessions.
Dependencies injected: none — module-level constants only.
Used by: npc_engine.engines.story_pacing.story_pacing_engine
"""

CYPHER_GET_ACTIVE_HIGH_SEVERITY_QUESTS = """
MATCH (q:Quest)
WHERE q.status <> 'completed'
  AND q.severity IS NOT NULL
  AND q.severity >= $threshold
RETURN q.id AS quest_id, q.severity AS severity
"""

CYPHER_GET_RECENT_MAJOR_EVENTS = """
MATCH (e:Event)
WHERE e.tick_id IS NOT NULL
  AND e.tick_id >= $min_tick_id
  AND e.severity >= $floor
RETURN e.id AS event_id, e.severity AS severity, e.tick_id AS tick_id
"""
