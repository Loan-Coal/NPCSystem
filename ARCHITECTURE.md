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
│                    FastAPI Application                          │
│   ┌──────────┐  ┌────────────┐  ┌──────────┐  ┌────────────┐  │
│   │  /health │  │ /dialogue  │  │  /clock  │  │   /batch   │  │
│   │          │  │ /ws/dialog │  │  /action │  │ /npc/{id}  │  │
│   └──────────┘  └─────┬──────┘  └────┬─────┘  └─────┬──────┘  │
│                        │              │               │         │
│   ┌────────────────────▼──────────────▼───────────────▼──────┐ │
│   │              api/dependencies.py                         │ │
│   │   (Composition root: wires DB, LLM, embeddings, auth)    │ │
│   └────────────────────────────────────────────────────────┬─┘ │
│   ┌─────────────────────────────────────────────────────────▼─┐ │
│   │                    auth/middleware.py                      │ │
│   │         Bearer token validation on all routes             │ │
│   └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                        │
          ┌─────────────┼──────────────────┐
          ▼             ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│  Dialogue    │ │   Gossip     │ │     Event        │
│  Engine      │ │   Engine     │ │     Engine       │
│              │ │              │ │                  │
│ session_store│ │pair_selector │ │  event_pool      │
│ context_     │ │gossip_distort│ │  location_scoper │
│  builder     │ │knowledge_    │ │  awareness_      │
│ prompt_      │ │  propagator  │ │   seeder         │
│  builder     │ │edge_updater  │ │  world_writer    │
│ llm_client   │ └──────┬───────┘ └────────┬─────────┘
│ response_    │        │                  │
│  parser      │        └──────┬───────────┘
│ action_      │               │
│  resolver    │               ▼
│ relation_    │    ┌──────────────────┐
│  mutator     │    │   scheduler/     │
│ emotion_     │    │  tick_scheduler  │
│  updater     │    │  game_clock      │
└──────┬───────┘    └──────────────────┘
       │
       │  All engines read/write through:
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Core Layer                                 │
│                                                                 │
│  ┌────────────────┐   ┌─────────────────────────────────────┐  │
│  │  retrieval/    │   │             graph/                  │  │
│  │                │   │                                     │  │
│  │ subgraph_      │   │ graph_writer (coordinator)          │  │
│  │  retriever     │   │  ├── character_writer               │  │
│  │ embedding_     │   │  ├── event_writer                   │  │
│  │  index         │   │  ├── relation_writer                │  │
│  │ vector_store   │   │  └── delta_log_writer               │  │
│  │ context_merger │   │                                     │  │
│  │ token_budget_  │   │ graph_reader                        │  │
│  │  enforcer      │   │ node_schemas / edge_schemas         │  │
│  │ context_       │   └──────────────────┬──────────────────┘  │
│  │  serializer    │                      │                      │
│  └────────────────┘                      │                      │
│                                          │                      │
│  ┌────────────────┐   ┌──────────────────▼──────────────────┐  │
│  │    world/      │   │               Neo4j                 │  │
│  │ world_reader   │   │         Knowledge Graph             │  │
│  │ world_writer   │   │  Character, Event, Location,        │  │
│  │ world_state    │   │  WorldState nodes                   │  │
│  └────────────────┘   │  RELATES_TO, KNOWS_ABOUT edges      │  │
│                        └─────────────────────────────────────┘  │
│  ┌────────────────┐   ┌─────────────────────────────────────┐  │
│  │  mutation/     │   │            engines/llm/             │  │
│  │ delta_log_mgr  │   │  LLMClientProtocol                  │  │
│  │ bounds_        │   │  ├── MistralAdapter                 │  │
│  │  validator     │   │  ├── LlamaAdapter                   │  │
│  └────────────────┘   │  ├── MockAdapter                    │  │
│                        │  └── factory.py                    │  │
│  ┌────────────────┐   └─────────────────────────────────────┘  │
│  │  engines/      │                                             │
│  │  emotion/      │                                             │
│  │ emotion_state  │                                             │
│  │ emotion_updater│                                             │
│  │ emotion_store  │                                             │
│  └────────────────┘                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Dialogue Pipeline — Sequence Diagram

```
Game Client          API Route       DialogueHandler      Neo4j       LLM
    │                    │                 │               │            │
    │── POST /dialogue──►│                 │               │            │
    │                    │── verify auth   │               │            │
    │                    │── get_session ─►│               │            │
    │                    │                 │── load session turns        │
    │                    │                 │               │            │
    │                    │                 │── Tier A fetch►│            │
    │                    │                 │◄── character, events, rel ──│
    │                    │                 │               │            │
    │                    │                 │── embed query ──────────────►
    │                    │                 │◄── Tier B RAG results ───────
    │                    │                 │               │            │
    │                    │                 │── world_reader►│            │
    │                    │                 │◄── world state ─────────────│
    │                    │                 │               │            │
    │                    │                 │── context_builder           │
    │                    │                 │   (merge→budget→serialize)  │
    │                    │                 │── prompt_builder            │
    │                    │                 │── llm_client ───────────────►
    │                    │                 │◄── structured JSON ──────────
    │                    │                 │               │            │
    │                    │                 │── response_parser (validate)│
    │                    │                 │── action_resolver           │
    │                    │                 │── relation_mutator ─────────►
    │                    │                 │── emotion_updater           │
    │                    │                 │── session_store.append      │
    │                    │                 │               │            │
    │◄── npc_response ──────────────────────               │            │
    │    action                           │               │            │
    │    facial_expression                │               │            │
```

---

## WebSocket Streaming — Event Sequence

```
Game Client                         WS Route                    LLM Stream
    │                                   │                           │
    │── connect /ws/dialogue ──────────►│                           │
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
    │                                   │── mutate graph             │
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
    │       └── Neo4j: query NPCs at shared locations
    │           → weight by gossipy field
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
    │       │       └── Neo4j: MERGE KNOWS_ABOUT edge on B→Event
    │       │           set knowledge_state, distorted_summary
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

### Adding a new distortion type
1. Add new `Literal` value to `GossipDistortion.distortion_type` in edge_schemas
2. Add template branch in `gossip_distort.py`
3. **No other file changes**

### Adding a new vector store backend
1. Create `retrieval/qdrant_vector_store.py` implementing `VectorStoreProtocol`
2. Add `"qdrant"` case to `retrieval/vector_store_factory.py`
3. **No other file changes**

### Adding a new NPC personality field
1. Add field to `CharacterNode` in `graph/node_schemas.py`
2. Add to seed data in `data/seed.py`
3. Use in relevant engine (e.g., new `cautious` field in `pair_selector.py`)
4. **No engine orchestrator changes**

### Adding a new relation variable (e.g., `respect`)
1. Add field to `RelationEdge` in `graph/edge_schemas.py`
2. Add to `DialogueResponseSchema.relation_deltas`
3. Add to `modifier_bounds_validator.py` bounds check
4. Add to `relation_writer.py` Cypher SET clause
5. **No dialogue handler changes**

---

## Deployment Notes

### Local Development
```bash
# Start Neo4j
docker run -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5

# Install and run
make install
make seed
make run

# Test WebSocket
wscat -c ws://localhost:8000/ws/dialogue \
  -H "Authorization: Bearer your_key"
```

### Game Engine Integration
- **Unity:** Use `UnityWebRequest` for REST, `NativeWebSocket` or `websocket-sharp` for WS.
  Parse JSON responses with `JsonUtility` or `Newtonsoft.Json`.
- **Unreal:** Use `FHttpModule` for REST, `IWebSocket` (built-in) for streaming.
  Deserialize with `FJsonObjectConverter`.

### Production Considerations
- Run behind a reverse proxy (nginx/Caddy) for TLS termination.
- Use Neo4j Enterprise for causal clustering if graph exceeds 100k nodes.
- Replace in-memory emotion/session stores with Redis for multi-instance deployments.
  (`emotion_store.py` and `session_store.py` are designed for easy Redis migration:
  same interface, swap the backend in the constructor.)
- Set `LOG_LLM_PROMPTS=false` and `ENV=prod` to prevent prompt logging.
- Configure `GOSSIP_RNG_SEED` and `EVENT_RNG_SEED` to `null` in production
  (random seeds) and to a fixed integer in testing (deterministic replays).

---

## Key Design Decisions (ADR Summary)

| Decision | Choice | Rationale |
|---|---|---|
| Graph database | Neo4j | Native graph traversal for relationship queries; Cypher is expressive for NPC knowledge |
| LLM interface | Protocol + factory | Swap Mistral for Llama (or cloud models) without touching engine code |
| Retrieval strategy | Hybrid (graph Tier A + RAG Tier B) | Facts from graph are authoritative; RAG provides semantic similarity for open-ended context |
| Gossip distortion | Deterministic pure function | Reproducible debugging; no LLM cost for NPC-to-NPC communication |
| Emotion persistence | In-memory store + graph snapshot | Fast reads during dialogue; survives restarts via Neo4j flush |
| WebSocket streaming | LLM token streaming | Eliminates perceived latency; players see NPC "thinking" in real time |
| Mutation bounds | Sliding window validator | Prevents LLM or exploit-driven stat manipulation; enforced independently of engine |
| Vector store | Protocol + in-memory default | Works out of the box; drop-in Qdrant for large deployments |
