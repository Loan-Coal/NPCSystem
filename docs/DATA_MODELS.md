# Data Models — NPC Engine Neo4j Knowledge Graph

This document is the authoritative reference for all nodes, edges, constraints,
and indexes in the Neo4j knowledge graph. Use this when implementing
`type_registry/base_nodes/*.yaml`, `type_registry/base_edges/*.yaml`,
`type_registry/runtime_models.py`, `data/seed.py`, and all Cypher queries.

---

## Schema Extensibility

The engine supports a **hybrid schema model**: core node and edge types are fixed in Python
(hardcoded field definitions, Pydantic models, Cypher constants), while game-specific
extensions are declared in `game_schema.yaml` and loaded at startup.

### Core vs Extension fields
- **Core fields**: defined in `type_registry/base_nodes/*.yaml` and `type_registry/base_edges/*.yaml`. Always present.
- **Extension fields**: `game_schema.yaml` expands base node and edge models and can add new node and edge types.
  Game-specific additions are validated through the type registry merge path and `graph/graph_edit_validator.py`.
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

### Type Registry Runtime Settings (`config.py`)

| Setting | Type | Default | Description |
|---|---|---|---|
| `TYPE_REGISTRY_EXTENSION_SOURCES` | string | `""` | Comma-delimited list of extension YAML file paths or glob patterns |

Runtime behavior:
- Package-internal base contracts are always loaded from `type_registry/base_nodes/*.yaml` and `type_registry/base_edges/*.yaml`.
- Base contracts support primitive fields and typed collection shapes: `list` + `items_type`, `dict` + `values_type`.
- Empty value means "base schema only" registry build.
- Non-empty value is resolved at startup, each source is loaded and validated fail-fast.
- Invalid source path/glob or invalid YAML shape aborts startup.

### TypeRegistry (`type_registry/contracts.py`)

Process-level immutable runtime snapshot built once at startup.

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | string | yes | Base schema version for the loaded registry snapshot |
| `base_node_types` | mapping | yes | Package-internal base node type definitions (required/null/type/range contract) |
| `base_edge_types` | mapping | yes | Package-internal base edge definitions including `src_type`/`dst_type` topology |
| `core_types` | mapping | yes | Core object types to immutable field-definition maps |
| `custom_node_types` | mapping | yes | Custom node type names to immutable field-definition maps |
| `custom_edge_types` | mapping | yes | Custom edge type names to immutable edge definitions (`src_type`, `dst_type`, fields) |
| `enum_extensions` | mapping | yes | Immutable enum extension values used by runtime validators |

Merge/validation rules enforced during startup build:
- Additive-only merges.
- Duplicate field-name collisions fail hard.
- Constraint mutation after first declaration fails hard.
- Singleton is immutable for the lifetime of the process.

R2 validation semantics (`type_registry/validation.py`):
- Edge endpoint compatibility is enforced from registry definitions (`src_type`, `dst_type`).
- Create/update reject missing required fields.
- Explicit null is forbidden for base fields and allowed for extension fields.
- Extension and base fields enforce primitive type/range constraints, and base collection shape constraints for typed lists/dicts.
- PATCH omits keep existing values; payload values are merged over existing state.

R3 limits and warnings:
- Each field definition now carries `max_bytes` (default `512`) and payload validation enforces UTF-8 encoded byte limits per field.
- Registry merge enforces extension field count cap (`16`) per object type.
- Missing extension values are emitted as structured warnings in API response metadata (`meta.warnings`), with corresponding structured logs and `graph_warnings_total` metric increments by `warning_code`.

R3 limits and warnings:
- Each field definition now carries `max_bytes` (default `512`) and payload validation enforces UTF-8 encoded byte limits per field.
- Registry merge enforces extension field count cap (`16`) per object type.
- Missing extension values are emitted as structured warnings in API response metadata (`meta.warnings`), with corresponding structured logs and `graph_warnings_total` metric increments by `warning_code`.

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

**Runtime model:** `CharacterNode` generated from `type_registry/runtime_models.py`

**Location** is tracked exclusively via the `LOCATED_AT` edge. There is no scalar `current_location_id` property on Character — the edge is the source of truth.

**Indexes:**
- Unique constraint on `id`
- Index on `faction`
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
| `event_type` | string | yes | — | Base values: `"crime"`, `"battle"`, `"trade"`, `"discovery"`. Extensible via `game_schema.yaml`. |
| `is_public` | bool | yes | true | False = secret; affects awareness seeding |
| `last_graph_updated_at` | datetime | yes | now() | Updated on every write |

**Participants** are tracked exclusively via `PARTICIPATED_IN` edges. There is no `participants` list property on Event — the edges are the source of truth.

**Immutable fields**: `id`, `location_id`, `occurred_at`, `tick_id`, `event_type`.

**Runtime model:** `EventNode` generated from `type_registry/runtime_models.py`

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

**Runtime model:** `LocationNode` generated from `type_registry/runtime_models.py`

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

## Generic Graph Mutation Bodies

Graph write endpoints now use generic registry-driven payload wrappers:

```python
class NodeWriteBody(BaseModel):
  properties: dict[str, Any] = Field(default_factory=dict)

class EdgeWriteBody(BaseModel):
  src_id: str
  dst_id: str
  properties: dict[str, Any] = Field(default_factory=dict)
```

Validation behavior:
- `properties` keys must exist in base or extension contracts for the target type.
- Required field checks, type/range checks, topology checks, and PATCH merge semantics are enforced by `type_registry.validation`.
- Unknown fields are rejected.

### Generic Graph Pagination Contract (`api/pagination.py`)

List routes use one isolated offset strategy resolver to keep pagination policy swappable.

| Field | Type | Default | Description |
|---|---|---|---|
| `strategy` | string | `offset` | Current pagination strategy identifier |
| `limit` | int | `50` | Page size (clamped to max `200`) |
| `offset` | int | `0` | Zero-based offset |
| `sort` | string | `id:asc` | Stable default ordering |

Returned in list route response metadata:
- `GET /v1/graph/nodes/{node_type}`
- `GET /v1/graph/edges/{edge_type}`

### Registry Introspection Endpoint

`GET /v1/schema/registry` returns serialized runtime registry snapshot:
- `schema_version`
- `node_types[]` with per-field entries `{ field_name, field_type, field_origin, required, max_bytes }`
- `edge_types[]` with topology (`src_type`, `dst_type`) plus field entries
- `enum_extensions`

### Generic Graph Pagination Contract (`api/pagination.py`)

List routes use one isolated offset strategy resolver to keep pagination policy swappable.

| Field | Type | Default | Description |
|---|---|---|---|
| `strategy` | string | `offset` | Current pagination strategy identifier |
| `limit` | int | `50` | Page size (clamped to max `200`) |
| `offset` | int | `0` | Zero-based offset |
| `sort` | string | `id:asc` | Stable default ordering |

Returned in list route response metadata:
- `GET /v1/graph/nodes/{node_type}`
- `GET /v1/graph/edges/{edge_type}`

### Registry Introspection Endpoint

`GET /v1/schema/registry` returns serialized runtime registry snapshot:
- `schema_version`
- `node_types[]` with per-field entries `{ field_name, field_type, field_origin, required, max_bytes }`
- `edge_types[]` with topology (`src_type`, `dst_type`) plus field entries
- `enum_extensions`

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

**`delta_log` cap and eviction policy:** Currently unbounded beyond the sliding window used by the bounds validator. Three design options (FIFO cap, DeltaEvent node, hybrid) are documented in `proposals/delta_log_options.md` — final design TBD pending selection.

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

Records current location of a character. This edge is the **sole source of truth** for location — there is no scalar `current_location_id` property on Character nodes.

| Property | Type | Required | Default | Description |
|---|---|---|---|---|
| `arrived_at` | datetime | yes | — | When the character arrived |
| `is_permanent_resident` | bool | yes | false | NPCs with a "home" location |

**Movement pattern:** There is no dedicated move route after generic cutover.
Clients should update location semantics through generic node/edge endpoints with
application-level coordination when atomic multi-write behavior is required.

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
MATCH (n:Character)
WHERE n.is_active = true AND n.id IS NOT NULL AND n.last_graph_updated_at IS NOT NULL
  AND (n.last_embedding_indexed_at IS NULL OR n.last_graph_updated_at > n.last_embedding_indexed_at)
RETURN n.id AS id, 'Character' AS kind
UNION ALL
MATCH (n:Event)
WHERE n.id IS NOT NULL AND n.last_graph_updated_at IS NOT NULL
  AND (n.last_embedding_indexed_at IS NULL OR n.last_graph_updated_at > n.last_embedding_indexed_at)
RETURN n.id AS id, 'Event' AS kind
UNION ALL
MATCH (n:Location)
WHERE n.id IS NOT NULL AND n.last_graph_updated_at IS NOT NULL
  AND (n.last_embedding_indexed_at IS NULL OR n.last_graph_updated_at > n.last_embedding_indexed_at)
RETURN n.id AS id, 'Location' AS kind
```

Note: inactive Characters (`is_active = false`) are excluded from embedding reconciliation.

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

---

## Phase 1 — Faction Graph Schema

Added in Phase 1.1. Factions are first-class graph entities that characters belong to,
that hold territory, and that maintain bidirectional standings toward each other.

### Faction Node (`type_registry/base_nodes/faction.yaml`)

Neo4j label: `Faction`

| Property | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique faction identifier |
| `name` | string | yes | Display name |
| `description` | string | no | Freeform description (≤500 chars, indexable for embeddings) |
| `archetype` | string | yes | One of: `religious`, `political`, `mercantile`, `military`, `criminal`, `social`, `other` |
| `is_active` | bool | yes | Soft-delete flag; inactive factions are excluded from context queries |
| `created_at` | string (ISO-8601) | yes | Node creation timestamp |
| `last_graph_updated_at` | string (ISO-8601) | yes | Last write timestamp, used for embedding reconciliation |

Uniqueness constraint: `Faction.id` (applied by `scripts/migrations/add_faction_support.py`).

Admin API: `POST /v1/admin/factions/` to create, `GET /v1/admin/factions/` to list,
`GET /v1/admin/factions/{faction_id}` to fetch by ID.

### MEMBER_OF Edge (`type_registry/base_edges/member_of.yaml`)

`(:Character)-[:MEMBER_OF {role, status, joined_at}]->(:Faction)`

| Property | Type | Required | Description |
|---|---|---|---|
| `role` | string | yes | One of: `leader`, `officer`, `member`, `recruit` |
| `status` | string | yes | One of: `active`, `exiled`, `deceased` |
| `joined_at` | string (ISO-8601) | yes | Timestamp when the edge was first created |

`joined_at` is set on creation and never updated. Re-calling the upsert only modifies
`role` and `status`.

Admin API: `POST /v1/admin/factions/{faction_id}/members` to add,
`DELETE /v1/admin/factions/{faction_id}/members/{character_id}` to remove,
`GET /v1/admin/factions/{faction_id}/members` to list.

### STANDS_WITH Edge (`type_registry/base_edges/stands_with.yaml`)

`(:Faction)-[:STANDS_WITH {standing, last_changed_at}]->(:Faction)`

| Property | Type | Required | Description |
|---|---|---|---|
| `standing` | int [-100, 100] | yes | -100 = at war, 0 = neutral, 100 = allied |
| `last_changed_at` | string (ISO-8601) | yes | Timestamp of last standing update |

**Bidirectional storage:** standings are stored as two independent directed edges.
A's standing toward B may differ from B's standing toward A (asymmetric diplomacy).

Admin API: `PUT /v1/admin/factions/{faction_id}/standings/{target_id}` to set (one direction),
`GET /v1/admin/factions/{faction_id}/standings` to list all outgoing standings.

### CONTROLS Edge (`type_registry/base_edges/controls.yaml`)

`(:Faction)-[:CONTROLS]->(:Location)`

No edge properties. Indicates territorial control. One location may be controlled by at
most one faction at a time (not enforced by the graph; enforced by game logic).

Admin API: `POST /v1/admin/factions/{faction_id}/controls/{location_id}` to set,
`DELETE /v1/admin/factions/{faction_id}/controls/{location_id}` to remove.
