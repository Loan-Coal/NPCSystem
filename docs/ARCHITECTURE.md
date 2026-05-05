# Architecture — NPC Engine

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Game Clients                             │
│          Unity (C#)              Unreal Engine (C++)            │
│      REST + WebSocket           REST + WebSocket                │
└───────────────────────┬─────────────────────────────────────────┘
                        │  HTTP / WebSocket
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Application  (/v1/*)                  │
│                                                                 │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌────────────┐   │
│  │  /health │  │ /dialogue  │  │  /clock  │  │   /batch   │   │
│  │          │  │ /ws/dialog │  │  /action │  │ /npc/{id}  │   │
│  └──────────┘  └─────┬──────┘  └────┬─────┘  └──────┬─────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  /v1/graph/*  (graph_write scope)                        │  │
│  │  POST|PATCH /characters  POST|PATCH /events              │  │
│  │  POST|PATCH /locations   PATCH /world_state              │  │
│  │  POST /edges/*           DELETE /edges/type/{s}/{d}      │  │
│  │  DELETE /characters/{id} (soft-delete)                   │  │
│  │  POST /characters/{id}/move   GET /schema                │  │
│  │  GET /characters  GET /events  GET /locations            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  /v1/graph/admin/*  (graph_admin scope ⊃ graph_write)    │  │
│  │  DELETE /characters/{id}  DELETE /events/{id}            │  │
│  │  DELETE /locations/{id}   PUT /relations/absolute        │  │
│  │  POST /relations/delta    POST /reindex                  │  │
│  │  GET /reindex/{job_id}    GET /audit_log                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│   ┌────────────────────────────────────────────────────────┐   │
│   │              api/dependencies.py                       │   │
│   │   (Composition root: wires DB, LLM, embeddings,       │   │
│   │    auth, loaded GameSchema)                            │   │
│   └────────────────────────────────────────────────────────┘   │
│   ┌────────────────────────────────────────────────────────┐   │
│   │                auth/middleware.py                       │   │
│   │   Bearer token + scope validation (admin ⊃ write)      │   │
│   │   + idempotency preflight on mutating /v1/* routes     │   │
│   └────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                        │
          ┌─────────────┼──────────────────────┐
          ▼             ▼                      ▼
┌──────────────┐ ┌──────────────┐  ┌───────────────────┐
│  Dialogue    │ │   Gossip     │  │      Event        │
│  Engine      │ │   Engine     │  │      Engine       │
│              │ │              │  │                   │
│ session_store│ │pair_selector │  │  event_pool       │
│ context_     │ │gossip_distort│  │  location_scoper  │
│  builder     │ │knowledge_    │  │  awareness_seeder │
│ prompt_      │ │  propagator  │  │  world_writer     │
│  builder     │ │edge_updater  │  └─────────┬─────────┘
│ llm_client   │ └──────┬───────┘            │
│ response_    │        └──────┬─────────────┘
│  parser      │               │
│ action_      │               ▼
│  resolver    │    ┌──────────────────┐
│ relation_    │    │   scheduler/     │
│  mutator     │    │  tick_scheduler  │
│ emotion_     │    │  game_clock      │
│  updater     │    └──────────────────┘
└──────┬───────┘
       │
       │  All engines read/write through:
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Core Layer                              │
│                                                                 │
│  ┌────────────────┐   ┌─────────────────────────────────────┐  │
│  │ graph_writer (coordinator)          │   │                                     │  │
│  │  ├── character/event/location       │   │                                     │  │
│  │  ├── relation/knowledge edges       │   │                                     │  │
│  │  └── transfer coordinators          │   │                                     │  │
│  │                                     │   │ graph_reader                        │  │
│  │                                     │   │ type_registry/runtime_models        │  │
│  │                                     │   │                                     │  │
│  │                                     │   │ generic_graph_service               │  │
│  │ vector_store   │   │ graph_reader                        │  │
│  │ context_merger │   │ type_registry/runtime_models        │  │
│  │ token_budget_  │   │                                     │  │
│  │  enforcer      │   │ generic_graph_service               │  │
│  │ context_       │   │ graph_admin_service                 │  │
│  │  serializer    │   │  └── delegates admin writes to      │  │
│  │ context_builder│   │      per-type graph services        │  │
│  └────────────────┘   │ generic_graph_utils                 │  │
│                        │ type_registry (contracts/validator) │  │
│  ┌────────────────┐   │ cascade_delete_service              │  │
│  │    world/      │   │ soft_delete_service                 │  │
│  │ world_reader   │   │ relation_mutation_service           │  │
│  │ world_writer   │   └──────────────────┬──────────────────┘  │
│  │ world_state    │                      │                      │
│  └────────────────┘                      ▼                      │
│                        ┌─────────────────────────────────────┐  │
│  ┌────────────────┐   │               Neo4j                 │  │
│  │   schema/      │   │         Knowledge Graph             │  │
│  │ schema_loader  │   │  Character, Event, Location,        │  │
│  │ schema_models  │   │  WorldState, custom node types      │  │
│  │ model_factory  │   │  RELATES_TO, KNOWS_ABOUT, edges     │  │
│  │ context_field_ │   │  + custom edge types                │  │
│  │  resolver      │   └─────────────────────────────────────┘  │
│  │ gossip_weight_ │                                             │
│  │  resolver      │   ┌─────────────────────────────────────┐  │
│  │ enum_validator │   │            engines/llm/             │  │
│  └────────────────┘   │  LLMClientProtocol                  │  │
│                        │  ├── MistralAdapter                 │  │
│  ┌────────────────┐   │  ├── LlamaAdapter                   │  │
│  │  mutation/     │   │  ├── OllamaAdapter                  │  │
│  │ delta_log_mgr  │   │  ├── MockAdapter                    │  │
│  │ bounds_        │   │  └── factory.py                     │  │
│  │  validator     │   └─────────────────────────────────────┘  │
│  └────────────────┘                                             │
│  ┌────────────────┐   ┌─────────────────────────────────────┐  │
│  │  engines/      │   │           auth/                     │  │
│  │  emotion/      │   │  api_key.py                         │  │
│  │ emotion_state  │   │  middleware.py                      │  │
│  │ emotion_updater│   │  permissions.py (scope inheritance) │  │
│  │ emotion_store  │   └─────────────────────────────────────┘  │
│  └────────────────┘                                             │
└─────────────────────────────────────────────────────────────────┘
```

### Type Registry Layer (R2-R4)

R2 introduces an immutable process-level registry package under `npc_engine/type_registry/`:

- `contracts.py` — extension/base document contracts and immutable runtime registry models.
- `base_nodes/*.yaml` — package-internal base node contracts (one file per base node type).
- `base_edges/*.yaml` — package-internal base edge contracts (one file per base edge type).
- Base contracts support primitive fields plus typed collection fields (`list` with `items_type`, `dict` with `values_type`).
- `base_contract_loader.py` — loader for package-internal base contracts.
- `extension_loader.py` — YAML source/path resolution and fail-fast document validation.
- `merge_rules.py` — additive-only merge semantics and duplicate/constraint-mutation rejection.
- `registry.py` — facade that builds one immutable registry snapshot from base schema + extension sources.
- `validation.py` — generic topology and payload validator for create/update/patch flows.
- `serializer.py` — stable client-facing serializer used by schema introspection endpoint.
- R3 limits: per-field UTF-8 byte caps (`max_bytes`, default `512`) and extension field count cap (`16` per object type).
- R3 warnings: missing extension values are emitted in API response metadata, structured logs, and `graph_warnings_total` metrics.
- R4 pagination isolation: `api/pagination.py` owns list pagination strategy defaults/bounds so future cursor migration does not leak into route/service logic.

Composition root wiring:

- `api/dependencies.py:get_type_registry()` builds one cached singleton.
- `main.py` lifespan now clears/loads the registry before connecting runtime services.
- `api/routes/system.py:/v1/schema/registry` exposes the serialized runtime registry snapshot.

---

## Auth Scope Model

Two scopes exist. `graph_admin` is a strict superset of `graph_write`.

```
graph_admin ⊃ graph_write
```

| Scope | Routes accessible |
|---|---|
| `graph_write` | All `/v1/graph/*` public routes (generic node/edge read-write + schema read) |
| `graph_admin` | Everything in `graph_write` + all `/v1/graph/admin/*` routes (hard delete, absolute relation, unbounded delta, reindex, audit log) |

Implementation: `auth/permissions.py` declares the scope hierarchy. `auth/middleware.py` checks
the highest matching scope. A single API key carries one scope value.

---

## v1.4 P0 Idempotency Contract and Persistence

v1.4 introduces middleware + persistence idempotency behavior in `auth/middleware.py` and
`engines/idempotency/*` for mutating `/v1/*` requests (`POST`, `PATCH`, `PUT`, `DELETE`) when
`IDEMPOTENCY_ENFORCE_HEADER=true`.

- Header required: `X-Idempotency-Key` (configurable via `IDEMPOTENCY_HEADER_NAME`)
- Accepted format: UUIDv4 string
- Missing header response: HTTP 400 + `IDEMPOTENCY_KEY_REQUIRED`
- Invalid format response: HTTP 422 + `IDEMPOTENCY_KEY_INVALID`
- Preflight decisions: `proceed`, `replay`, `conflict`, `in_flight`
- Persistence backend: Neo4j `IdempotencyRecord` keyed by `(idempotency_key, resource_scope)`
- Finalization stores terminal response (`completed` or `failed_terminal`) for replay safety
- Expired record cleanup runs in background (`IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS`)
- Scope/auth behavior is unchanged: auth still resolves before idempotency checks
- `OPTIONS` preflight requests are always exempt

---

## v1.4 P1 Context Relevance and Budget Pipeline

P1 introduces deterministic context ranking and tier-aware budget enforcement in the dialogue
path via:

- `engines/dialogue/context_relevance_engine.py`
- `retrieval/context_budget_enforcer.py`
- `retrieval/context_builder.py`

Dialogue flow behavior:

- Tier assembly:
  - `tier0`: world + emotion snapshot.
  - `tierA`: graph-authoritative context + session turns.
  - `tierB`: vector retrieval context.
- Deterministic relevance scoring uses weighted components from `LLMConfig.relevance_weights`.
- Tie-break ordering is stable: score DESC, then `node_type` ASC, then `node_id` ASC.
- Tier A and session turns are non-compressible.
- Tier budget enforcement uses `LLMConfig.tier_budget_tokens` and `session_turns_budget_tokens`.
- Compression cache keys are canonicalized as:
  `(node_id, node_type, prompt_schema_version, compression_prompt_version)`.
- Tier A overflow raises a typed context budget error before LLM invocation.

This keeps prompt assembly deterministic and budget-safe while preserving high-priority context.

---

## Schema Layer — Startup Sequence

```
Service start
    │
    ├── schema_loader.load(GAME_SCHEMA_PATH)
    │       ├── parse YAML → validate against SchemaConfig (Pydantic meta-schema)
    │       ├── check required core type declarations
    │       └── FAIL FAST with specific errors if invalid
    │
    ├── type_registry.build(base_schema, TYPE_REGISTRY_EXTENSION_SOURCES)
    │       ├── load package-internal base contracts (`base_nodes/*.yaml`, `base_edges/*.yaml`)
    │       ├── resolve configured extension file/glob sources
    │       ├── parse + validate extension YAML documents
    │       ├── enforce additive-only merges
    │       ├── reject duplicate field collisions and constraint mutations
    │       └── expose immutable singleton registry for runtime consumers
    │
    ├── llm_config_loader.load(LLM_CONFIG_PATH)
    │       ├── parse YAML → validate against LLMConfig model
    │       └── FAIL FAST with specific errors if invalid
    │
    ├── graph_db.connect()
    │
    ├── redis_runtime.connect()  # optional; non-idempotency cache runtime
    │
    ├── idempotency_service.ensure_constraints()
    │       └── CREATE CONSTRAINT IF NOT EXISTS on (idempotency_key, resource_scope)
    │
    ├── model_factory.generate_models(schema)
    │       └── for each custom_node_type: create_model(...) → cached Pydantic model
    │
    ├── enum_validator.build(schema)
    │       └── merge base Literals + enum_extensions → merged validator per field
    │
    ├── context_field_resolver.build(schema)
    │       └── maps tier → [fields] for subgraph_retriever + context_serializer
    │
    ├── gossip_weight_resolver.build(schema)
    │       └── collects all fields tagged gossip_weight → averaged by pair_selector
    │
    ├── Neo4j index auto-creation
    │       └── for each custom field with indexed: true → CREATE INDEX IF NOT EXISTS
    │
    ├── start background tasks
    │       ├── embedding_reconciler.start(interval=EMBEDDING_RECONCILE_INTERVAL_SECONDS)
    │       │   ├── scans Character|Event|Location where last_graph_updated_at > last_embedding_indexed_at
    │       │   ├── re-embeds stale rows into vector store
    │       │   └── persists node.last_embedding_indexed_at after successful upsert
    │       └── idempotency_cleanup_scheduler.start(interval=IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS)
    │           └── deletes expired IdempotencyRecord rows
    │
    └── Register all routers in main.py with API_V1_PREFIX
```

---

## game_schema.yaml Format

```yaml
schema_version: "1.0"

core_types:
  character:
    extension_fields:
      guild_rank:
        type: int          # str | int | float | bool
        range: [1, 10]     # optional, int/float only
        default: 1
        description: "Character's rank in their guild (1=novice, 10=grandmaster)"
        semantics: [context_tier_a]     # context_tier_a | context_tier_0 | gossip_weight
        indexed: false                  # whether to create a Neo4j index
      bravery:
        type: int
        range: [0, 100]
        default: 50
        description: "Willingness to take risks; affects gossip pair weighting"
        semantics: [gossip_weight]
  world_state:
    extension_fields:
      plague_active:
        type: bool
        default: false
        description: "Whether a plague is currently spreading"
        semantics: [context_tier_0]

enum_extensions:
  event_type:         [ritual, coronation, betrayal]
  participation_role: [spy, mediator]
```

---

## Future: Custom Types

`game_schema.yaml` supports declaring `custom_node_types` and `custom_edge_types` (e.g. `Faction`, `MEMBER_OF`). The schema parser loads and validates them at startup, and the generic graph API stores and returns them. However, **current engines do not consume custom types** — gossip, dialogue, event, and quest engines operate only on the five built-in node types (Character, Event, Location, WorldState) and their standard edges.

This means:
- Custom node/edge data is stored and queryable.
- Custom nodes are **not** included in LLM context, gossip pair selection, or event awareness seeding.
- Custom edges are **not** cascade-deleted unless declared in `cascade_on_delete`.

A startup warning is emitted if custom types are declared:
```
WARN: custom_node_types declared (['Faction']) but not consumed by current engines.
```

Custom type consumption by engines is planned for a later milestone.

Example (not currently consumed):
```yaml
custom_node_types:
  Faction:
    fields:
      id:      { type: str,  required: true }
      name:    { type: str,  required: true }
      standing:{ type: int,  range: [0, 100], default: 50 }

custom_edge_types:
  MEMBER_OF:
    src_type: Character
    dst_type: Faction
    cascade_on_delete: [Character]
    directional: true
    fields:
      rank: { type: str }
```

---

## Dialogue Pipeline — Sequence Diagram

```
Game Client          API Route       DialogueHandler      Neo4j       LLM
    │                    │                 │               │            │
    │── POST /v1/dialogue►│                │               │            │
    │                    │── verify auth   │               │            │
    │                    │── get_session ─►│               │            │
    │                    │                 │── load session turns       │
    │                    │                 │               │            │
    │                    │                 │── Tier A fetch►│           │
    │                    │                 │◄── char(active), events, rel│
    │                    │                 │               │            │
    │                    │                 │── embed query ─────────────►
    │                    │                 │◄── Tier B RAG results ──────
    │                    │                 │               │            │
    │                    │                 │── world_reader►│           │
    │                    │                 │◄── world state ─────────────│
    │                    │                 │               │            │
    │                    │                 │── context_field_resolver   │
    │                    │                 │   (schema-driven field sel)│
    │                    │                 │── context_builder          │
    │                    │                 │   (merge→budget→serialize) │
    │                    │                 │── prompt_builder           │
    │                    │                 │── llm_client ──────────────►
    │                    │                 │◄── structured JSON ─────────
    │                    │                 │               │            │
    │                    │                 │── response_parser (validate)│
    │                    │                 │── action_resolver           │
    │                    │                 │── relation_mutator (bounded)│─►Neo4j
    │                    │                 │── emotion_updater           │
    │                    │                 │── session_store.append      │
    │                    │                 │               │            │
    │◄── npc_response ─────────────────────                │            │
    │    action                            │               │            │
    │    facial_expression                 │               │            │
```

---

## Graph Write Pipeline — Sequence Diagram

```
Game Client          API Route      GenericGraphService      Neo4j
    │                    │                  │               │              │
    │── POST /v1/graph/──►│                 │               │              │
  │   nodes/character   │                 │               │              │
    │                    │── verify auth    │               │              │
    │                    │   (graph_write)  │               │              │
    │                    │── validate body  │               │              │
  │                    │   (generic body) │               │              │
  │                    │                  │── registry validate          │
  │                    │                  │── MERGE node ─►              │
    │                    │                  │◄── result ─────              │
    │                    │                  │── commit tx ──►              │
  │◄── 200 OK ───────────────────────────                 │              │
```

---

## Soft-Delete Flow

```
Public character soft-delete route was removed in generic graph cutover.
Character deletion is currently admin-only.


DELETE /v1/graph/admin/characters/{id}  (graph_admin scope, mode=hard)
    │
    ├── cascade_delete_service.delete(character_id)
    │       ├── Read schema.custom_edge_types for cascade rules
    │       ├── DELETE all RELATES_TO, KNOWS_ABOUT, LOCATED_AT, PARTICIPATED_IN
    │       ├── DELETE all custom edges where cascade_on_delete includes Character
    │       ├── DELETE character node
    │       └── commit (single atomic transaction)
    │
    ├── embedding_index.invalidate(character_id)
    └── return {deleted_node_id, deleted_edges, deleted_nodes, audit_id}
```

---

## WebSocket Streaming — Event Sequence

```
Game Client                         WS Route                    LLM Stream
    │                                   │                           │
    │── connect /v1/ws/dialogue ───────►│                           │
    │── send {player_id, npc_id, msg} ─►│                           │
    │                                   │── build context           │
    │                                   │── build prompt            │
    │                                   │── llm.stream() ──────────►│
    │◄── {type:"token", data:"I "} ─────│◄── token ─────────────────│
    │◄── {type:"token", data:"think"} ──│◄── token ─────────────────│
    │◄── {type:"token", data:"..."} ────│◄── ... ───────────────────│
    │                                   │◄── [stream complete] ──────│
    │                                   │── parse full response      │
    │                                   │── resolve action           │
    │                                   │── mutate graph (bounded)   │
    │◄── {type:"action", data:{...}} ───│                           │
    │◄── {type:"expression", data:{}}───│                           │
    │◄── {type:"done"} ────────────────►│                           │
```

---

## Gossip Tick — Data Flow

```
tick_scheduler
    │
    ▼
gossip_handler.run_tick(tick_id)
    │
    ├── pair_selector.select_pairs(tick_id)
    │       └── Neo4j: query active NPCs (is_active=true) at shared locations
    │           → weight by gossip_weight_resolver fields (default: gossipy)
    │           → RNG-sample N pairs (seeded by tick_id)
    │
    ├── For each pair (A, B):
    │       ├── gossip_handler.select_event_to_share(sharer=A)
    │       │       └── Neo4j: get A's known events sorted by recency
    │       │           → weight by gossipy + recency
    │       │
    │       ├── gossip_distort(
    │       │       event_summary, sharer_honesty, trust, severity, tick_id, base
    │       │   ) → GossipDistortion (pure function, no I/O)
    │       │
    │       ├── knowledge_propagator.propagate(B, event, distortion)
    │       │       └── (only if B.is_active = true)
    │       │           Neo4j: MERGE KNOWS_ABOUT edge on B→Event
    │       │
    │       ├── edge_updater.log_gossip(A, B, tick_id)
    │       │       └── Neo4j: update A→B RELATES_TO delta_log
    │       │
    │       └── embedding_index.invalidate(B.id)
    │
    └── logger.info("gossip_tick_complete", pairs=N, distortions=K, tick=tick_id)
```

---

## Extension Points (Open/Closed Design)

### Adding a new LLM backend
1. Create `engines/llm/openai_adapter.py` implementing `LLMClientProtocol`
2. Add `"openai"` case to `engines/llm/factory.py`
3. Add `OPENAI_API_URL` to `config.py`
4. **No other file changes**

### Adding a custom NPC personality field
1. Add field to `game_schema.yaml` under `core_types.character.extension_fields`
2. Tag with `semantics: [gossip_weight]` if it should affect gossip, `[context_tier_a]` for LLM context
3. Restart service — schema_loader validates and gossip_weight_resolver/context_field_resolver update automatically
4. **No code changes**

### Adding a custom node type (e.g. Faction)
1. Add to `game_schema.yaml` under `custom_node_types`
2. Declare any custom edge types under `custom_edge_types` with cascade rules
3. Restart service — model_factory generates Pydantic models; API routes handle the type generically
4. **No code changes**

### Adding a new relation variable (e.g. `respect`)
1. Add field to `RelationEdge` via registry contract YAML and runtime model generation in `type_registry/runtime_models.py`
2. Add to `DialogueResponseSchema.relation_deltas`
3. Add to `modifier_bounds_validator.py` bounds check
4. Add to `relation_writer.py` Cypher SET clause
5. **No engine orchestrator changes**

### Adding a new distortion type
1. Update gossip distortion type definition in `engines/gossip/gossip_distort.py`
2. Add template branch in `gossip_distort.py`
3. **No other file changes**

### Adding a new vector store backend
1. Create `retrieval/qdrant_vector_store.py` implementing `VectorStoreProtocol`
2. Add `"qdrant"` case to `retrieval/vector_store_factory.py`
3. **No other file changes**

---

## Deployment Notes

### Local Development
```bash
# Copy and edit schema config
cp game_schema.example.yaml game_schema.yaml

# Start Neo4j
docker run -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5

# Install and run
make install
make seed
make run

# Test WebSocket
wscat -c ws://localhost:8000/v1/ws/dialogue \
  -H "Authorization: Bearer your_key"
```

### Environment Variables (v1.4 P0 additions)
```
GAME_SCHEMA_PATH=/app/game_schema.yaml   # required; path to schema config file
LLM_CONFIG_PATH=/app/config/llm_config.yaml
API_V1_PREFIX=/v1                        # default; prefix for all routes
API_KEY_GRAPH_WRITE=write_scope_key       # optional; dedicated write-scope key
API_KEY_GRAPH_ADMIN=admin_scope_key       # optional; dedicated admin-scope key
EMBEDDING_RECONCILE_INTERVAL_SECONDS=300
IDEMPOTENCY_ENFORCE_HEADER=false
IDEMPOTENCY_HEADER_NAME=X-Idempotency-Key
IDEMPOTENCY_PENDING_TIMEOUT_SECONDS=30
IDEMPOTENCY_RETENTION_HOURS=24
IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS=3600
REDIS_ENABLED=false
REDIS_URL=redis://localhost:6379/0
REDIS_CONNECT_TIMEOUT_SECONDS=1.0
```

### Game Engine Integration
- **Unity:** Use `UnityWebRequest` for REST, `NativeWebSocket` or `websocket-sharp` for WS.
  All routes now under `/v1/` prefix. Parse JSON responses with `JsonUtility` or `Newtonsoft.Json`.
  Call `GET /v1/schema` on SDK initialization to discover available node types and fields.
- **Unreal:** Use `FHttpModule` for REST, `IWebSocket` (built-in) for streaming.
  Deserialize with `FJsonObjectConverter`.

### Production Considerations
- Run behind a reverse proxy (nginx/Caddy) for TLS termination.
- Use Neo4j Enterprise for causal clustering if graph exceeds 100k nodes.
- Replace in-memory emotion/session stores with Redis for multi-instance deployments.
- Set `LOG_LLM_PROMPTS=false` and `ENV=prod` to prevent prompt logging.
- Mount `game_schema.yaml` as a read-only volume; do not bake it into the image.
- The embedding reconciler runs as a background asyncio task — no separate process needed.

---

## Key Design Decisions (ADR Summary)

| Decision | Choice | Rationale |
|---|---|---|
| Graph database | Neo4j | Native graph traversal for relationship queries; Cypher is expressive for NPC knowledge |
| LLM interface | Protocol + factory | Swap Mistral for Llama (or cloud models) without touching engine code |
| Local LLM backend | Mixtral 8x7B (quantized, llama.cpp/Ollama) | Solo deployment, privacy/offline goals; prompt iteration prioritized over latency at this stage |
| Retrieval strategy | Hybrid (graph Tier A + RAG Tier B) | Facts from graph are authoritative; RAG provides semantic similarity for open-ended context |
| Gossip distortion | Deterministic pure function | Reproducible debugging; no LLM cost for NPC-to-NPC communication |
| Emotion persistence | In-memory store + graph snapshot | Fast reads during dialogue; survives restarts via Neo4j flush |
| WebSocket streaming | LLM token streaming | Eliminates perceived latency; players see NPC "thinking" in real time |
| Mutation bounds | Sliding window validator (dialogue) / unbounded admin (game events) | Prevents LLM exploit via dialogue; designers need full control for scripted events |
| Vector store | Protocol + in-memory default | Works out of the box; drop-in Qdrant for large deployments |
| Schema extensibility | Hybrid: fixed core + config-driven extensions | Engine algorithms always work (semantic deps satisfied); game devs customize without code changes |
| Soft delete | `is_active` flag on Character | Preserves NPC memory history; hard delete is admin cleanup only |
| Embedding reconciliation | Timestamp-based background reconciler | Self-healing after crashes; no outbox infrastructure required |
| Route versioning | All routes under `/v1/` | Clean versioned surface; enables future `/v2/` without breaking existing integrations |
| Scope inheritance | `graph_admin ⊃ graph_write` | Single privileged key for developers; no dual-key management |
| Edge DELETE | Path parameters per edge type | RESTful; proxy-safe; no request body on DELETE |
| PATCH body typing | Typed models + `extension_fields` dict | Core fields statically typed; custom fields dynamically validated against schema |
| Location source of truth | `LOCATED_AT` edge only | Removed `Character.current_location_id` scalar — edge is authoritative, scalar was redundant |
| Event participants source of truth | `PARTICIPATED_IN` edge only | Removed `Event.participants` list property — edge is authoritative, list property was redundant |

---

## Dialogue Degradation Tiers

Dialogue requests degrade through tiers if upstream components are slow or unavailable.

| Tier | Condition | Context | Latency target |
|---|---|---|---|
| `full` | Normal operation | Graph Tier A + RAG Tier B + LLM | `DIALOGUE_FULL_TIMEOUT_SECONDS` (default 30s) |
| `graph_only` | RAG unavailable or full tier timeout | Graph Tier A + LLM (no RAG) | `DIALOGUE_GRAPH_ONLY_TIMEOUT_SECONDS` (default 15s) |
| `canned` | Neo4j unavailable or graph_only timeout | Pre-written archetype response from `prompts/canned/<archetype>.yaml` | < 50 ms |

The `degradation_level` field is returned in every `DialogueResponse`. When the canned tier fires, relation mutation and emotion updates are skipped (the graph may be unavailable).

Implementation: `engines/dialogue/degradation.py` + `engines/dialogue/dialogue_handler.py`.

Metric: `dialogue_degradation_level_total{level=full|graph_only|canned}`

---

## Prompt Management

Prompt templates live in `prompts/`. Two sub-directories:

| Directory | Contents |
|---|---|
| `prompts/canned/` | Per-archetype canned response YAML files (`default.yaml`, `guard.yaml`, etc.) Used by degradation tier 3. |
| `prompts/<engine>/` | Versioned LLM prompt templates (not yet extracted — see `proposals/prompt_inventory.md`) |

**Editing a canned response:** edit the relevant `prompts/canned/<archetype>.yaml` and restart (no code change needed).

**Adding a new archetype:** create `prompts/canned/<new_archetype>.yaml` following the existing format. The degradation module will pick it up automatically; the handler passes `archetype="default"` for now (TODO: derive archetype from graph at runtime).
