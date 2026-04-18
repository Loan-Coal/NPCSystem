# Data Models — NPC Engine Neo4j Knowledge Graph

This document is the authoritative reference for all nodes, edges, constraints,
and indexes in the Neo4j knowledge graph. Use this when implementing `graph/node_schemas.py`,
`graph/edge_schemas.py`, `data/seed.py`, and all Cypher queries.

---

## Schema Extensibility

The engine supports a **hybrid schema model**: core node and edge types are fixed in Python
(hardcoded field definitions, Pydantic models, Cypher constants), while game-specific
extensions are declared in `game_schema.yaml` and loaded at startup.

### Core vs Extension fields
- **Core fields**: defined in `graph/node_schemas.py`. Always present. Validated statically by Pydantic.
- **Extension fields**: declared in `game_schema.yaml` under `core_types.{type}.extension_fields`.
  Validated at runtime by `schema/enum_validator.py` and `graph/graph_edit_validator.py`.
  Stored in Neo4j alongside core fields.

### Custom node and edge types
Game developers may declare additional node types (e.g. `Faction`, `Item`) and edge types
(e.g. `MEMBER_OF`, `OWNS`) in `game_schema.yaml`. These are stored and queryable via the
graph API but are **not** processed by gossip, dialogue, or event algorithms unless they
carry semantic annotations (see `game_schema.yaml` format in `ARCHITECTURE.md`).

### Semantic annotations
Extension fields may declare a `semantics` list in the schema config:
- `context_tier_a` — field value + description is included in the LLM dialogue context (Tier A).
- `context_tier_0` — always included in every prompt, like WorldState fields.
- `gossip_weight` — field is included in gossip personality averaging alongside `gossipy`.
  All `gossip_weight` fields are averaged with equal weight by `schema/gossip_weight_resolver.py`.

### Enum extensions
Base enum values for `event_type` and `participation_role` are hardcoded Pydantic Literals.
Game developers may append valid values via `game_schema.yaml`:
```yaml
enum_extensions:
  event_type: [ritual, coronation, betrayal]
  participation_role: [spy, mediator]
```
`schema/enum_validator.py` builds a merged validator at startup; invalid values return HTTP 422
with the full list of accepted values in `error.details.accepted_values`.

---

## Soft-Delete Semantics

Characters support soft-deletion via the `is_active` flag. Setting `is_active=false`:
- Excludes the character from gossip pair selection (`WHERE c.is_active = true` in all queries).
- Excludes the character from event awareness seeding.
- Excludes the character from dialogue context retrieval.
- Prevents the character from being a knowledge propagation target.
- Returns HTTP 410 Gone from `GET /v1/npc/{id}/state`.

All edges connected to an inactive character are **preserved**. Other NPCs retain their
`KNOWS_ABOUT`, `RELATES_TO`, and `PARTICIPATED_IN` history involving the deactivated character.

Hard delete (admin-only) permanently removes the node and all connected edges in one atomic
transaction and should only be used for permanent graph cleanup.

---

## Embedding Reconciliation

Every node carries a `last_graph_updated_at` timestamp, updated on every write.
Successful reconciliation also stamps `last_embedding_indexed_at` on each graph node.
`retrieval/embedding_reconciler.py` runs every `EMBEDDING_RECONCILE_INTERVAL_SECONDS`
(default: 300s) and re-queues any node where
`last_graph_updated_at > last_embedding_indexed_at` (or where `last_embedding_indexed_at` is null).

This makes embedding staleness self-healing after crashes or missed invalidations.
The admin reindex endpoint (`POST /v1/graph/admin/reindex`) remains for manual full refresh.

---

## v1.4 P0 Runtime Config Models

These models are validated at startup and are not Neo4j graph entities.

### LLMConfig (`schema/llm_config_models.py`)

Loaded from `LLM_CONFIG_PATH` via `schema/llm_config_loader.py`.

| Field | Type | Required | Description |
|---|---|---|---|
| `prompt_schema_version` | string | yes | Prompt schema contract version used by builders/parsers |
| `compression_prompt_version` | string | yes | Compression template version |
| `tier_budget_tokens.tier_a` | int > 0 | yes | Tier A token budget |
| `tier_budget_tokens.tier_b` | int > 0 | yes | Tier B token budget |
| `tier_budget_tokens.tier_c` | int > 0 | yes | Tier C token budget |
| `session_turns_budget_tokens` | int > 0 | yes | Tier A sub-budget for session turn memory |
| `compression_trigger_ratio` | float (0,1] | yes | Threshold for compression trigger |
| `max_proximity_hops` | int >= 0 | yes | Graph-hop cap for proximity score contribution |
| `relevance_weights` | object | yes | Deterministic scoring weights (must sum to 1.0) |

Startup behavior: invalid or missing LLM config fails fast during application startup.

### Idempotency Runtime Settings (`config.py`)

| Setting | Type | Default | Description |
|---|---|---|---|
| `IDEMPOTENCY_ENFORCE_HEADER` | bool | `false` | Enables/disables v1.4 transport preflight checks |
| `IDEMPOTENCY_HEADER_NAME` | string | `X-Idempotency-Key` | Header name checked by middleware |
| `IDEMPOTENCY_PENDING_TIMEOUT_SECONDS` | int > 0 | `30` | Max age for a `pending` record before the request can proceed again |
| `IDEMPOTENCY_RETENTION_HOURS` | int > 0 | `24` | Retention window for persisted idempotency records |
| `IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS` | int > 0 | `3600` | Cleanup cadence for deleting expired records |

Runtime behavior: middleware preflight delegates to `IdempotencyService` for decisions
(`proceed`, `replay`, `conflict`, `in_flight`) and persists terminal responses for replay.

### IdempotencyRecord (`engines/idempotency/models.py`, Neo4j label `IdempotencyRecord`)

| Property | Type | Required | Description |
|---|---|---|---|
| `idempotency_key` | string (UUIDv4) | yes | Request idempotency key from header |
| `resource_scope` | string | yes | Method+path scope (`METHOD:/v1/...`) |
| `request_hash` | string (sha256) | yes | Hash of method/path/query/body |
| `status` | enum | yes | `pending`, `completed`, `failed_terminal` |
| `response_status_code` | int | no | Cached terminal HTTP status for replay |
| `response_body` | string | no | Cached terminal response body for replay |
| `response_hash` | string (sha256) | no | Integrity hash of status+body |
| `created_at` | datetime | yes | Record creation timestamp |
| `expires_at` | datetime | yes | Expiry timestamp used by cleanup |
| `pending_timeout_seconds` | int > 0 | yes | In-flight timeout window |
| `updated_at` | datetime | no | Last terminal write timestamp |

Constraints and indexes:
- Unique constraint on `(idempotency_key, resource_scope)`.

### Redis Runtime Settings (`config.py`)

| Setting | Type | Default | Description |
|---|---|---|---|
| `REDIS_ENABLED` | bool | `false` | Enables optional Redis runtime connection |
| `REDIS_URL` | string | `redis://localhost:6379/0` | Redis endpoint for non-idempotency caches |
| `REDIS_CONNECT_TIMEOUT_SECONDS` | float > 0 | `1.0` | Connect timeout for startup ping |

Runtime behavior: startup attempts Redis connect only when enabled and degrades gracefully
when unavailable.

### Engine Contract Model (`engines/contracts/contract_models.py`)

Contract YAML documents under `engines/contracts/*.yaml` are validated against required fields:

- `name`
- `version`
- `inputs`
- `outputs`
- `side_effects`
- `idempotency`
- `auth_scope`
- `error_contract`
- `tests`

Validation command: `make check-contracts`.

### P1 Context Budget Runtime Models

These are runtime-only models used during prompt context assembly.

#### ContextRelevanceCandidate (`engines/dialogue/context_relevance_engine.py`)

| Field | Type | Required | Description |
|---|---|---|---|
| `node_id` | string | yes | Stable node identifier for tie-break ordering |
| `node_type` | string | yes | Stable node type for tie-break ordering |
| `item` | `ContextItem` | yes | Context payload + tier metadata |
| `recency` | float [0,1] | yes | Normalized recency component |
| `severity` | float [0,1] | yes | Normalized severity component |
| `proximity_hops` | int >= 0 | yes | Graph-hop proximity input |
| `relation` | float [0,1] | yes | Relation relevance component |
| `quest` | float [0,1] | yes | Quest involvement component |
| `explicit` | float [0,1] | yes | Explicit context boost component |

Scoring:
- Score = weighted sum using `LLMConfig.relevance_weights`.
- Deterministic tie-break: `node_type` ASC, then `node_id` ASC.

#### ContextBudgetError (`retrieval/context_budget_enforcer.py`)

| Field | Type | Required | Description |
|---|---|---|---|
| `tier` | string | yes | Budget tier that failed (`tier_a`, `session_turns`, etc.) |
| `used_tokens` | int | yes | Observed token usage |
| `budget_tokens` | int | yes | Configured token budget for tier |
| `detail` | string | yes | Human-readable diagnostics |

#### Compression Cache Key (`retrieval/context_budget_enforcer.py`)

Canonical key tuple:

`(node_id, node_type, prompt_schema_version, compression_prompt_version)`

This key format is used for deterministic cache lookup during Tier B/Tier C compression.

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
| `is_active` | bool | yes | true | False = soft-deleted; excluded from all runtime engine queries |
| `created_at` | datetime | yes | now() | |
| `updated_at` | datetime | yes | now() | Updated on any mutation |
| `last_graph_updated_at` | datetime | yes | now() | Updated on every write; used by embedding reconciler |
| **Personality** | | | | |
| `gossipy` | int [0–100] | yes | 50 | Probability weight for gossip selection |
| `credulity` | int [0–100] | yes | 50 | How readily the NPC believes rumors |
| `honesty` | int [0–100] | yes | 50 | Inversely affects gossip distortion probability |
| **Emotion** (snapshot) | | | | |
| `current_mood` | string | no | "neutral" | Last known mood label (emotion engine is authoritative) |

**Immutable fields** (cannot be patched after creation): `id`, `is_player`, `created_at`.

**Pydantic model:** `CharacterNode` in `graph/node_schemas.py`

**Indexes:**
- Unique constraint on `id`
- Index on `faction`
- Index on `current_location_id`
- Index on `is_active` (used in every engine query filter)

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
| `event_type` | string | yes | — | Base values: `"crime"`, `"battle"`, `"trade"`, `"discovery"`. Extensible via `game_schema.yaml`. |
| `is_public` | bool | yes | true | False = secret; affects awareness seeding |
| `last_graph_updated_at` | datetime | yes | now() | Updated on every write |

**Immutable fields**: `id`, `location_id`, `occurred_at`, `tick_id`, `event_type`, `participants`.

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
| `last_graph_updated_at` | datetime | yes | now() | Updated on every write |

**Immutable fields**: `id`.

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
| `last_graph_updated_at` | datetime | yes | now() | Updated on every write |

**PATCH semantics for JSON fields:** `faction_standings` and `active_conditions` use
**full-replace** semantics on PATCH. The submitted value replaces the stored value entirely.
To change one faction's standing, send the full dict with all factions included.

**Pydantic model:** `WorldState` in `world/world_state.py`

---

## Patch Body Models

Each resource type has a dedicated, fully typed patch request model. All fields are Optional.
Immutable fields are absent from the model — they cannot be submitted at all.
Extension fields from `game_schema.yaml` are accepted via a separate `extension_fields` dict
sub-object, validated at runtime against the loaded schema.

```python
class CharacterPatchBody(BaseModel):
    name: str | None = None
    archetype: str | None = None
    faction: str | None = None
    biography: str | None = None
    current_location_id: str | None = None
    gossipy: int | None = Field(None, ge=0, le=100)
    credulity: int | None = Field(None, ge=0, le=100)
    honesty: int | None = Field(None, ge=0, le=100)
    current_mood: str | None = None
    is_active: bool | None = None
    extension_fields: dict[str, Any] | None = None  # validated against GameSchema at runtime
    meta: MutationMeta

class EventPatchBody(BaseModel):
    summary: str | None = None
    severity: int | None = Field(None, ge=0, le=100)
    is_public: bool | None = None
    extension_fields: dict[str, Any] | None = None
    meta: MutationMeta

class LocationPatchBody(BaseModel):
    name: str | None = None
    region: str | None = None
    descriptor: str | None = None
    location_tag: str | None = None
    extension_fields: dict[str, Any] | None = None
    meta: MutationMeta
```

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
  "cause_type": "dialogue | game_event | gossip",
  "deltas": {"trust": -5, "fear": 10, "affection": 0},
  "clamped": false,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

**`cause_type` values:**
- `"dialogue"` — change applied by the dialogue engine (bounded per-turn and per-window).
- `"game_event"` — change applied via `POST /v1/graph/admin/relations/delta` (unbounded, clamped to [0,100]).
- `"gossip"` — change applied by the gossip engine.

**Clamping log:** If an admin delta would push a value past [0,100], `clamped: true` is set
in the log entry, and the response includes `meta.clamped_fields: list[str]`.

**Seeding rule:** Initialize `relevance_score = 1.0` if same faction, `0.5` if same location, `0.0` otherwise.

---

### KNOWS_ABOUT (Character → Event)

Records that a character has knowledge (factual or rumor) about an event.

| Property | Type | Required | Default | Description |
|---|---|---|---|---|
| `knowledge_state` | enum | yes | — | `"knows"` (factual) or `"rumor"` (possibly distorted) |
| `distortion_type` | string | no | null | If rumor: `"omission"`, `"exaggeration"`, `"role_swap"`, `"timeline_shift"` |
| `distortion_level` | int [0–100] | no | null | Degree of distortion |
| `distorted_summary` | string | no | null | What the character believes happened |
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

**Movement pattern:** Use `POST /v1/graph/characters/{id}/move` for atomic location changes.
This endpoint deletes the old LOCATED_AT edge, creates a new one, and updates
`character.current_location_id` in a single transaction. Do not use separate API calls.

---

### PARTICIPATED_IN (Character → Event)

Records that a character directly participated in (witnessed or caused) an event.

| Property | Type | Required | Default | Description |
|---|---|---|---|---|
| `role` | Literal | yes | — | `"perpetrator"`, `"victim"`, `"witness"`, `"bystander"`. Extensible via `game_schema.yaml`. |
| `participated_at` | datetime | yes | — | |

---

## Referential Integrity

All edge-creation Cypher queries enforce node existence **inside the transaction** using MATCH
before MERGE. There is no pre-read existence check (TOCTOU risk). Pattern:

```cypher
MATCH (a:Character {id: $src_id})
MATCH (b:Character {id: $dst_id})
MERGE (a)-[r:RELATES_TO]->(b)
SET r += $props
RETURN r
```

If either MATCH returns nothing, `graph_writer.py` raises `NodeNotFoundError(node_id=...)`.
This applies to all edge types including custom edges declared in `game_schema.yaml`.

---

## Example Cypher Queries

These are the canonical query patterns. Use these exact forms in `graph_reader.py`.
**All character queries MUST include `WHERE c.is_active = true`.**

### Get active character with direct relations
```cypher
MATCH (c:Character {id: $npc_id})
WHERE c.is_active = true
OPTIONAL MATCH (c)-[r:RELATES_TO]->(other:Character)
WHERE other.is_active = true
RETURN c, collect({relation: r, character: other}) AS relations
```

### Get events known by a character
```cypher
MATCH (c:Character {id: $npc_id})-[k:KNOWS_ABOUT]->(e:Event)
WHERE c.is_active = true
RETURN e, k.knowledge_state, k.distorted_summary
ORDER BY e.occurred_at DESC
LIMIT $limit
```

### Get location context with present active NPCs
```cypher
MATCH (loc:Location {id: $location_id})
OPTIONAL MATCH (c:Character)-[:LOCATED_AT]->(loc)
WHERE c.is_active = true
RETURN loc, collect(c) AS present_npcs
```

### Get NPC-player directed edge
```cypher
MATCH (npc:Character {id: $npc_id})-[r:RELATES_TO]->(p:Character {id: $player_id})
WHERE npc.is_active = true
RETURN r
```

### Gossip pair selection (active NPCs at shared locations only)
```cypher
MATCH (a:Character)-[:LOCATED_AT]->(loc:Location)<-[:LOCATED_AT]-(b:Character)
WHERE a.id <> b.id
  AND a.is_player = false AND b.is_player = false
  AND a.is_active = true AND b.is_active = true
RETURN a, b, loc
```

### Embedding reconciliation scan
```cypher
MATCH (n)
WHERE n.last_graph_updated_at > $last_reconcile_at
RETURN n.id, labels(n)[0] AS node_type
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

---

## Seed Data Requirements

`data/seed.py` must create:

1. **Locations** — at least 5 distinct locations with varied `location_tag` values.
2. **Characters** — at least 10 NPCs plus 1 player character.
   - Each NPC must have `gossipy`, `credulity`, `honesty` values that vary meaningfully.
   - Each NPC must have `is_active=true` and a LOCATED_AT edge to a starting location.
   - Include at least 2 NPCs per location.
3. **RELATES_TO edges** — for every pair of NPCs who share a location or faction,
   create A→B and B→A with neutral values (trust=50, fear=50, affection=50)
   and `relevance_score` computed from faction/proximity.
4. **Events** — at least 3 historical events with PARTICIPATED_IN and KNOWS_ABOUT edges.
5. **WorldState** — one node with epoch="age_of_peace", empty conditions.
6. **Extension fields** — if `game_schema.yaml` declares extension fields with defaults,
   seed data must include those defaults on all seeded nodes.

All seed functions must be idempotent: running seed.py twice must not create duplicates.
Use `MERGE` instead of `CREATE` in all seed Cypher.
