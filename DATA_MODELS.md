# Data Models — NPC Engine Neo4j Knowledge Graph

This document is the authoritative reference for all nodes, edges, constraints,
and indexes in the Neo4j knowledge graph. Use this when implementing `graph/node_schemas.py`,
`graph/edge_schemas.py`, `data/seed.py`, and all Cypher queries.

---

## Node Types

### Character

Represents an NPC or the player character.

| Property | Type | Required | Default | Description |
|---|---|---|---|---|
| `id` | string (UUID) | yes | — | Unique identifier |
| `name` | string | yes | — | Display name |
| `archetype` | string | yes | — | e.g. "merchant", "guard", "elder", "assassin" |
| `faction` | string | no | null | Faction affiliation |
| `biography` | string | yes | — | Short character lore (used in prompts) |
| `current_location_id` | string | yes | — | FK to Location.id |
| `is_player` | bool | yes | false | True for the player character node |
| `created_at` | datetime | yes | now() | |
| `updated_at` | datetime | yes | now() | Updated on any mutation |
| **Personality** | | | | |
| `gossipy` | int [0–100] | yes | 50 | Probability weight for gossip selection |
| `credulity` | int [0–100] | yes | 50 | How readily the NPC believes rumors |
| `honesty` | int [0–100] | yes | 50 | Inversely affects gossip distortion probability |
| **Emotion** (snapshot) | | | | |
| `current_mood` | string | no | "neutral" | Last known mood label (emotion engine is authoritative) |

**Pydantic model:** `CharacterNode` in `graph/node_schemas.py`

**Indexes:**
- Unique constraint on `id`
- Index on `faction`
- Index on `current_location_id`

---

### Event

Represents something that happened in the world.

| Property | Type | Required | Default | Description |
|---|---|---|---|---|
| `id` | string (UUID) | yes | — | Unique identifier |
| `summary` | string | yes | — | Human-readable event description |
| `severity` | int [0–100] | yes | — | 0 = trivial, 100 = world-altering |
| `location_id` | string | yes | — | Where the event occurred |
| `occurred_at` | datetime | yes | — | Game time of occurrence |
| `tick_id` | int | yes | — | Gossip/event tick when created |
| `participants` | list[string] | yes | [] | Character IDs involved |
| `event_type` | string | yes | — | e.g. "crime", "battle", "trade", "discovery" |
| `is_public` | bool | yes | true | False = secret; affects awareness seeding |

**Pydantic model:** `EventNode` in `graph/node_schemas.py`

**Indexes:**
- Unique constraint on `id`
- Index on `location_id`
- Index on `occurred_at`
- Index on `severity`

---

### Location

Represents a place in the game world.

| Property | Type | Required | Default | Description |
|---|---|---|---|---|
| `id` | string (UUID) | yes | — | Unique identifier |
| `name` | string | yes | — | Display name |
| `region` | string | no | null | Broader geographic area |
| `location_tag` | string | yes | — | Used in event_pool.json matching (e.g. "tavern", "market") |
| `descriptor` | string | yes | — | Short description used in prompts |

**Pydantic model:** `LocationNode` in `graph/node_schemas.py`

**Indexes:**
- Unique constraint on `id`
- Index on `location_tag`

---

### WorldState

Singleton node. Only one instance exists.

| Property | Type | Required | Default | Description |
|---|---|---|---|---|
| `id` | string | yes | "world" | Fixed ID |
| `epoch` | string | yes | "age_of_peace" | Current era/epoch name |
| `faction_standings` | JSON string | yes | "{}" | Dict of faction → standing int |
| `active_conditions` | JSON string | yes | "[]" | List of active world conditions |
| `weather` | string | yes | "clear" | Global weather condition |
| `last_updated_at` | datetime | yes | now() | |

**Pydantic model:** `WorldState` in `world/world_state.py`

---

## Edge Types

### RELATES_TO (Character → Character)

Directed trust/fear/affection relationship between two characters.
**Always created in both directions:** A→B and B→A with independent values.

| Property | Type | Required | Default | Description |
|---|---|---|---|---|
| `trust` | int [0–100] | yes | 50 | Neutral = 50, 0 = deep mistrust, 100 = absolute trust |
| `fear` | int [0–100] | yes | 50 | 0 = fearless, 100 = terrified |
| `affection` | int [0–100] | yes | 50 | 0 = hatred, 100 = deep love/friendship |
| `interaction_count` | int | yes | 0 | Total dialogue exchanges |
| `delta_log` | JSON string | yes | "[]" | Last N delta events (list of dicts) |
| `last_updated_at` | datetime | yes | now() | |
| `relevance_score` | float | yes | 0.0 | Computed: higher for shared faction or proximity |

**Delta log entry format:**
```json
{
  "tick_id": 42,
  "cause_id": "event_uuid_or_dialogue_session_id",
  "deltas": {"trust": -5, "fear": 10, "affection": 0},
  "timestamp": "2024-01-01T00:00:00Z"
}
```

**Seeding rule:** Initialize `relevance_score = 1.0` if same faction, `0.5` if same location, `0.0` otherwise.

---

### KNOWS_ABOUT (Character → Event)

Records that a character has knowledge (factual or rumor) about an event.

| Property | Type | Required | Default | Description |
|---|---|---|---|---|
| `knowledge_state` | enum | yes | — | `"knows"` (factual) or `"rumor"` (possibly distorted) |
| `distortion_type` | string | no | null | If rumor: "omission", "exaggeration", "role_swap", "timeline_shift" |
| `distortion_level` | int [0–100] | no | null | Degree of distortion |
| `distorted_summary` | string | no | null | What the character believes happened (may differ from Event.summary) |
| `learned_at_tick` | int | yes | — | Tick when character learned this |
| `source_character_id` | string | no | null | Who told them (null if they witnessed it) |

---

### LOCATED_AT (Character → Location)

Records current location of a character.
(Also redundantly stored on Character.current_location_id for fast lookup.)

| Property | Type | Required | Default | Description |
|---|---|---|---|---|
| `arrived_at` | datetime | yes | — | When the character arrived |
| `is_permanent_resident` | bool | yes | false | NPCs with a "home" location |

---

### PARTICIPATED_IN (Character → Event)

Records that a character directly participated in (witnessed or caused) an event.

| Property | Type | Required | Default | Description |
|---|---|---|---|---|
| `role` | string | yes | — | "perpetrator", "victim", "witness", "bystander" |
| `participated_at` | datetime | yes | — | |

---

## Example Cypher Queries

These are the canonical query patterns. Use these exact forms in `graph_reader.py`.

### Get character with direct relations
```cypher
MATCH (c:Character {id: $npc_id})
OPTIONAL MATCH (c)-[r:RELATES_TO]->(other:Character)
RETURN c, collect({relation: r, character: other}) AS relations
```

### Get events known by a character
```cypher
MATCH (c:Character {id: $npc_id})-[k:KNOWS_ABOUT]->(e:Event)
RETURN e, k.knowledge_state, k.distorted_summary
ORDER BY e.occurred_at DESC
LIMIT $limit
```

### Get location context with present NPCs
```cypher
MATCH (loc:Location {id: $location_id})
OPTIONAL MATCH (c:Character)-[:LOCATED_AT]->(loc)
RETURN loc, collect(c) AS present_npcs
```

### Get NPC-player directed edge
```cypher
MATCH (npc:Character {id: $npc_id})-[r:RELATES_TO]->(p:Character {id: $player_id})
RETURN r
```

### Apply relation delta (parameterized)
```cypher
MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id})
SET r.trust = $new_trust,
    r.fear = $new_fear,
    r.affection = $new_affection,
    r.interaction_count = r.interaction_count + 1,
    r.last_updated_at = datetime(),
    r.delta_log = $new_delta_log
```

### Get gossip-eligible NPC pairs (shared location)
```cypher
MATCH (a:Character)-[:LOCATED_AT]->(loc:Location)<-[:LOCATED_AT]-(b:Character)
WHERE a.id <> b.id AND a.is_player = false AND b.is_player = false
RETURN a, b, loc
```

---

## Seed Data Requirements

`data/seed.py` must create:

1. **Locations** — at least 5 distinct locations with varied `location_tag` values.
2. **Characters** — at least 10 NPCs plus 1 player character.
   - Each NPC must have `gossipy`, `credulity`, `honesty` values that vary meaningfully.
   - Each NPC must have a LOCATED_AT edge to a starting location.
   - Include at least 2 NPCs per location.
3. **RELATES_TO edges** — for every pair of NPCs who share a location or faction,
   create A→B and B→A with neutral values (trust=50, fear=50, affection=50)
   and `relevance_score` computed from faction/proximity.
4. **Events** — at least 3 historical events with PARTICIPATED_IN and KNOWS_ABOUT edges.
5. **WorldState** — one node with epoch="age_of_peace", empty conditions.

All seed functions must be idempotent: running seed.py twice must not create duplicates.
Use `MERGE` instead of `CREATE` in all seed Cypher.
