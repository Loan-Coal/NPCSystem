"""
seed_queries.py - Cypher query constants for the idempotent world seeder.

Does NOT: execute queries or manage database connections.

Dependencies injected: None.
"""

CYPHER_SEED_LOCATIONS = """
UNWIND $locations AS location
MERGE (loc:Location {id: location.id})
SET loc += location
"""

CYPHER_SEED_CHARACTERS = """
UNWIND $characters AS character
MERGE (c:Character {id: character.id})
SET c += character
"""

CYPHER_SEED_LOCATED_AT = """
UNWIND $pairs AS pair
MATCH (c:Character {id: pair.character_id}), (loc:Location {id: pair.location_id})
MERGE (c)-[r:LOCATED_AT]->(loc)
SET r.arrived_at = datetime(), r.is_permanent_resident = pair.is_permanent_resident
"""

CYPHER_SEED_WORLD = """
MERGE (w:WorldState {id: 'world'})
SET w.epoch = 'age_of_peace',
    w.faction_standings = '{}',
    w.active_conditions = '[]',
    w.weather = 'clear',
    w.last_updated_at = datetime()
"""

CYPHER_SEED_RELATIONS = """
MATCH (a:Character), (b:Character)
WHERE a.id <> b.id
    AND a.is_player = false
    AND b.is_player = false
OPTIONAL MATCH (a)-[:LOCATED_AT]->(loc_a:Location)
OPTIONAL MATCH (b)-[:LOCATED_AT]->(loc_b:Location)
WITH a, b,
     (a.faction = b.faction) AS same_faction,
     (loc_a IS NOT NULL AND loc_a = loc_b) AS same_location
WHERE same_faction OR same_location
MERGE (a)-[r:RELATES_TO]->(b)
SET r.trust = 50,
        r.fear = 50,
        r.affection = 50,
        r.interaction_count = coalesce(r.interaction_count, 0),
        r.delta_log = '[]',
        r.last_updated_at = datetime(),
        r.relevance_score = CASE
            WHEN same_faction THEN 1.0
            WHEN same_location THEN 0.5
            ELSE 0.0
        END
"""

CYPHER_SEED_EVENTS = """
UNWIND $events AS event
MERGE (e:Event {id: event.id})
SET e += event
"""

CYPHER_SEED_PARTICIPATION = """
UNWIND $participation AS row
MATCH (c:Character {id: row.character_id}), (e:Event {id: row.event_id})
MERGE (c)-[p:PARTICIPATED_IN]->(e)
SET p.role = row.role,
        p.participated_at = datetime()
"""

CYPHER_SEED_KNOWLEDGE = """
UNWIND $knowledge AS row
MATCH (c:Character {id: row.character_id}), (e:Event {id: row.event_id})
MERGE (c)-[k:KNOWS_ABOUT]->(e)
SET k.knowledge_state = row.knowledge_state,
        k.learned_at_tick = row.learned_at_tick,
        k.distortion_type = row.distortion_type,
        k.distortion_level = row.distortion_level,
        k.distorted_summary = row.distorted_summary,
        k.source_character_id = row.source_character_id
"""
